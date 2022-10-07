from .models import Storage, Step, HopCalculation
from math import exp
import logging
from django.db import transaction

AMOUNT_FACTOR = 100

def glenn_tinseth_hop(charge, hop, progress, ibu):
    boiltime = charge.recipe.boiltime.total_seconds() - progress
    #logging.debug("%s(bt) min = %s(total_bt) - %s(progr)", boiltime/60, charge.recipe.boiltime.total_seconds(), progress)

    utilization = 10
    ### 10% higher utilization of hop, when pellets are used.
    ### Currently we're not distingush between pellets and dolden. Therefore pellet is always true.
    utilization += utilization/100*10 if True else 0

    ### 10% higher utilization of hop, when added after 15min.
    utilization += utilization/100*10 if (progress/60) >= 15 else 0

    A = (ibu * charge.amount) / (hop.alpha * utilization)
    B = (1.65 * pow(0.000125, (0.004 * charge.recipe.wort)))
    C = (1-exp((-0.04) * boiltime /60)) / (4.15)
    #logging.debug("Formula_A: %s = (%s * %s)/ (%s * %s)", A, ibu, charge.amount, hop.alpha, utilization)
    #logging.debug("Formula_B: %s = (1.65 * pow(0.000125, (0.004 * %s)))", B, charge.recipe.wort)
    #logging.debug("Formula_C: %s = (1 - exp( (-0.04) * %s /60 )) / 4.15", C, boiltime)
    calculated_hop = A / (B * C)

    ### units are important!!!
    calculated_hop /= 1000 if hop.unit.name == "kg" else 1

    return round(calculated_hop,2)

def glenn_tinseth_ibu(charge, hop, progress, amount):
    boiltime = charge.recipe.boiltime.total_seconds() - progress
    ### units are important!!!
    amount *= 1000 if hop.unit.name == "kg" else 1

    utilization = 10
    ### 10% higher utilization of hop, when pellets are used.
    ### Currently we're not distingush between pellets and dolden. Therefore pellet is always true.
    utilization += utilization/100*10 if True else 0

    ### 10% higher utilization of hop, when added after 15min.
    utilization += utilization/100*10 if (progress/60) >= 15 else 0

    #logging.debug("%s(bt) min = %s(total_bt) - %s(progr)", boiltime/60, charge.recipe.boiltime.total_seconds(), progress)
    A = (amount * hop.alpha * (utilization)) /  charge.amount
    B = (1.65 * pow(0.000125, (0.004 * charge.recipe.wort)))
    C = (1-exp((-0.04) * boiltime /60)) / (4.15)
    #logging.debug("Formula_A: %s = (%s * %s * %s) / %s", A, amount, hop.alpha, utilization, charge.amount)
    #logging.debug("Formula_B: %s = (1.65 * pow(0.000125, (0.004 * %s)))", B, charge.recipe.wort)
    #logging.debug("Formula_C: %s = (1 - exp( (-0.04) * %s /60 )) / 4.15", C, boiltime)
    ibu = round(A * B * C, 1)

    return ibu


@transaction.atomic
def calculate_ingredients(charge):
    step = Step.objects.get(pk=charge.recipe.first)
    ingredients = {}
    progress = 0
    counting = 0
    total_ibu = 0
    calc_hops = list()
    savepoint = transaction.savepoint()
    while step:
        data = list()
        if step.duration and step.category.name == "Würzekochung":
            if step.duration:
                progress += step.duration.total_seconds()

        if step.ingredient:
            required_amount = charge.amount * step.amount / AMOUNT_FACTOR
            ### Calculate hops
            if step.category.name == "Würzekochung":
                if not charge.hop_calculation_finished:
                    hop = Storage.objects.get(id=step.ingredient.id)
                    finished = False
                    hops = Storage.objects.filter(name=step.ingredient.name).order_by('-amount')
                    ### Calculate IBU of current step, which is required by the recipe
                    target_step_ibu = glenn_tinseth_ibu(charge, step.ingredient, progress, required_amount)
                    remaining_ibu = target_step_ibu
                    for hop in hops:
                        if finished:
                            break
                        if hop.amount == 0:
                            continue
                        calculated_hop = list()
                        ### Calculate possible IBU with available hop in stock
                        possible_ibu = glenn_tinseth_ibu(charge, hop, progress, hop.amount)
                        logging.debug("%s: %s %s %s a=%s für %s min ergibt IBU = %s. Gebraucht wird IBU = %s",
                            step.title, hop.amount, hop.unit, hop.name, hop.alpha,
                            (charge.recipe.boiltime.total_seconds() - progress)/60,
                            possible_ibu, target_step_ibu)
                        if remaining_ibu > possible_ibu:
                            remaining_ibu -= possible_ibu
                            calc_hop_amount = glenn_tinseth_hop(charge, hop, progress, possible_ibu)
                            calc_hop_ibu = glenn_tinseth_ibu(charge, hop, progress, calc_hop_amount)
                            hop.amount = 0
                            total_ibu += possible_ibu
                        else:
                            calc_hop_amount = glenn_tinseth_hop(charge, hop, progress, remaining_ibu)
                            calc_hop_ibu = glenn_tinseth_ibu(charge, hop, progress, calc_hop_amount)
                            finished = True
                            hop.amount -= calc_hop_amount
                            total_ibu += remaining_ibu
                        calculated_hop.append(hop.id)
                        calculated_hop.append(calc_hop_amount)
                        calculated_hop.append(hop.unit.name)
                        calculated_hop.append(calc_hop_ibu)
                        calculated_hop.append(step.id)
                        hop.save()
                        calc_hops.append(calculated_hop)

            ### Calcualte other ingredients
            else:
                data.append(step.ingredient.name)
                data.append(required_amount)
                data.append(step.ingredient.unit.name)

                if step.ingredient.type in ingredients:
                    tmp = ingredients[step.ingredient.type]
                    tmp.append(data)
                    ingredients[step.ingredient.type] = tmp
                else:
                    tmp = list()
                    tmp.append(data)
                    ingredients[step.ingredient.type] = tmp
        if hasattr(step, 'next'):
            step = step.next
        else:
            break
    ingredients['Wasser'] = [['Hauptguss', charge.recipe.hg * charge.amount / AMOUNT_FACTOR, 'Liter'],
                             ['Nachguss', charge.recipe.ng * charge.amount / AMOUNT_FACTOR, 'Liter']]

    transaction.savepoint_rollback(savepoint)
    if not charge.hop_calculation_finished:
        for calculated_hop in calc_hops:
            logging.debug("Item: %s", calculated_hop)
            logging.debug("Item: %s", calculated_hop[4])
            store_it = HopCalculation()
            store_it.charge = charge
            store_it.step = Step.objects.get(id=calculated_hop[4])
            store_it.ingredient = Storage.objects.get(id=calculated_hop[0])
            store_it.amount = calculated_hop[1]
            store_it.ibu = calculated_hop[3]
            store_it.save()

        charge.hop_calculation_finished = True
        charge.save()
    return ingredients
