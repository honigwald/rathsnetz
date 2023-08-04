from django.db import models
#from .charge import Charge
from .step import RecipeStep
from .storage import Storage
from .protocol import BrewProtocol
from django.db import transaction
from math import exp
from datetime import datetime
import logging


AMOUNT_FACTOR = 100

class HopCalculation(models.Model):
    id = models.AutoField(primary_key=True)
    charge = models.CharField(max_length=50, default="")
    step = models.ForeignKey(RecipeStep, on_delete=models.DO_NOTHING, blank=True, null=True)
    amount = models.FloatField()
    ibu = models.FloatField()

    def __str__(self):
        return str(self.charge_id) + "_" + str(self.step.step)




def glenn_tinseth_hop(charge, hop, progress, ibu):
    boiltime = charge.recipe.boiltime.total_seconds() - progress
    # logging.debug("{}(bt) min = {}(total_bt) - {}(progr)".format(
    #    boiltime/60, charge.recipe.boiltime.total_seconds(), progress))

    utilization = 10
    # 10% higher utilization of hop, when pellets are used.
    # Currently we're not distingush between pellets and dolden. Therefore pellet is always true.
    utilization += utilization / 100 * 10 if True else 0

    # 10% higher utilization of hop, when added after 15min.
    utilization += utilization / 100 * 10 if (progress / 60) >= 15 else 0

    A = (ibu * charge.amount) / (hop.alpha * utilization)
    B = 1.65 * pow(0.000125, (0.004 * charge.recipe.wort))
    C = (1 - exp((-0.04) * boiltime / 60)) / (4.15)
    # logging.debug("Formula_A: {} = ({} * {})/ ({} * {})".format(
    #    A, ibu, charge.amount, hop.alpha, utilization))
    # logging.debug("Formula_B: %s = (1.65 * pow(0.000125, (0.004 * %s)))", B, charge.recipe.wort)
    # logging.debug("Formula_C: %s = (1 - exp( (-0.04) * %s /60 )) / 4.15", C, boiltime)
    calculated_hop = A / (B * C)

    # units are important!!!
    calculated_hop /= 1000 if hop.unit.name == "kg" else 1

    return round(calculated_hop, 2)


def glenn_tinseth_ibu(charge, hop, progress, amount):
    boiltime = charge.recipe.boiltime.total_seconds() - progress
    # units are important!!!
    amount *= 1000 if hop.unit.name == "kg" else 1

    utilization = 10
    # 10% higher utilization of hop, when pellets are used.
    # Currently we're not distingush between pellets and dolden. Therefore pellet is always true.
    utilization += utilization / 100 * 10 if True else 0

    # 10% higher utilization of hop, when added after 15min.
    utilization += utilization / 100 * 10 if (progress / 60) >= 15 else 0

    # logging.debug("{}(bt) min = {}(total_bt) - {}(progr)".format(
    #    boiltime/60, charge.recipe.boiltime.total_seconds(), progress))
    A = (amount * hop.alpha * (utilization)) / charge.amount
    B = 1.65 * pow(0.000125, (0.004 * charge.recipe.wort))
    C = (1 - exp((-0.04) * boiltime / 60)) / (4.15)
    # logging.debug("Formula_A: {} = ({} * {})/ ({} * {})".format(
    #    A, ibu, charge.amount, hop.alpha, utilization))
    # logging.debug("Formula_B: %s = (1.65 * pow(0.000125, (0.004 * %s)))", B, charge.recipe.wort)
    # logging.debug("Formula_C: %s = (1 - exp( (-0.04) * %s /60 )) / 4.15", C, boiltime)
    ibu = round(A * B * C, 1)

    return ibu


@transaction.atomic
def calculate_ingredients(charge):
    step = charge.recipe.first_step
    ingredients = {}
    progress = 0
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
            # Calculate hops
            if step.category.name == "Würzekochung":
                if not charge.hop_calculation_finished:
                    hop = Storage.objects.get(id=step.ingredient.id)
                    finished = False
                    hops = Storage.objects.filter(name=step.ingredient.name).order_by(
                        "-amount"
                    )
                    # Calculate IBU of current step, which is required by the recipe
                    target_step_ibu = glenn_tinseth_ibu(
                        charge, step.ingredient, progress, required_amount
                    )
                    remaining_ibu = target_step_ibu
                    for hop in hops:
                        if finished:
                            break
                        if hop.amount == 0:
                            continue
                        calculated_hop = list()
                        # Calculate possible IBU with available hop in stock
                        possible_ibu = glenn_tinseth_ibu(
                            charge, hop, progress, hop.amount
                        )
                        logging.debug(
                            "%s: %s %s %s a=%s für %s min ergibt IBU = %s. Gebraucht wird IBU = %s",
                            step.title,
                            hop.amount,
                            hop.unit,
                            hop.name,
                            hop.alpha,
                            (charge.recipe.boiltime.total_seconds() - progress) / 60,
                            possible_ibu,
                            target_step_ibu,
                        )
                        if remaining_ibu > possible_ibu:
                            remaining_ibu -= possible_ibu
                            calc_hop_amount = glenn_tinseth_hop(
                                charge, hop, progress, possible_ibu
                            )
                            calc_hop_ibu = glenn_tinseth_ibu(
                                charge, hop, progress, calc_hop_amount
                            )
                            hop.amount = 0
                            total_ibu += possible_ibu
                        else:
                            calc_hop_amount = glenn_tinseth_hop(
                                charge, hop, progress, remaining_ibu
                            )
                            calc_hop_ibu = glenn_tinseth_ibu(
                                charge, hop, progress, calc_hop_amount
                            )
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

            # Calcualte other ingredients
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
        if hasattr(step, "next"):
            step = step.next
        else:
            break
    ingredients["Wasser"] = [
        ["Hauptguss", charge.recipe.hg * charge.amount / AMOUNT_FACTOR, "Liter"],
        ["Nachguss", charge.recipe.ng * charge.amount / AMOUNT_FACTOR, "Liter"],
    ]

    transaction.savepoint_rollback(savepoint)
    if not charge.hop_calculation_finished:
        for calculated_hop in calc_hops:
            logging.debug("Item: %s", calculated_hop)
            logging.debug("Item: %s", calculated_hop[4])
            store_it = HopCalculation()
            store_it.charge_id = charge
            store_it.step = RecipeStep.objects.get(id=calculated_hop[4])
            store_it.ingredient = Storage.objects.get(id=calculated_hop[0])
            store_it.amount = calculated_hop[1]
            store_it.ibu = calculated_hop[3]
            store_it.save()

        charge.hop_calculation_finished = True
        charge.save()
    return ingredients


AMOUNT_FACTOR = 100


def load_calculated_hopping(step, hopping):
    logging.debug("load_calculated_hopping")
    step.amount = hopping[0].amount
    step.ingredient = hopping[0].ingredient
    step.description = "Hopfenrechner: " + str(hopping[0].ibu) + " IBU"
    return step


# HELPER FUNCTION
def get_steps(rid, charge, amount):
    try:
        step = RecipeStep.objects.get(pk=rid.first)
    except RecipeStep.DoesNotExist:
        step = None
    s = []
    while step:
        if step.ingredient:
            try:
                hops = HopCalculation.objects.filter(charge=charge).filter(step=step)
            except HopCalculation.DoesNotExist:
                hops = None
            if hops:
                for idx, hop in enumerate(hops):
                    if idx:
                        add_step = RecipeStep.objects.get(id=step.id)
                        step.next = add_step
                        step = add_step
                    step.description = str(hop.ibu) + "_berechnet"
                    step.amount = hop.amount
                    step.ingredient = hop.ingredient
                    s.append(step)
            else:
                step.amount = (step.amount * amount) / AMOUNT_FACTOR
                s.append(step)
        else:
            s.append(step)
        try:
            step = step.next
        except AttributeError:
            step = None
    return s


def get_next_step(charge, step):
    try:
        hopping = HopCalculation.objects.filter(charge=charge).filter(step=step)
        if step.category.name == "Würzekochung" and hopping and len(hopping) > 1:
            next_step = RecipeStep.objects.get(id=step.id)
            next_step.description = str(hopping[1].ibu) + "_berechnet"
            next_step.amount = hopping[1].amount
            next_step.ingredient = hopping[1].ingredient
            return next_step
        else:
            next_step = step.next
            logging.debug("brewing: get_next_step: %s", next_step)
            next_step.amount = (
                (next_step.amount * charge.amount) / AMOUNT_FACTOR
                if next_step.amount
                else next_step.amount
            )
            hopping = HopCalculation.objects.filter(charge=charge).filter(
                step=next_step
            )
            if step.category.name == "Würzekochung" and hopping:
                logging.debug("brewing: get_next_step: get calculated hoppings.")
                # next_step = Step.objects.get(id=step.id)
                next_step.description = str(hopping[0].ibu) + "_berechnet"
                next_step.amount = hopping[0].amount
                next_step.ingredient = hopping[0].ingredient
    except RecipeStep.DoesNotExist:
        next_step = None

    return next_step


def protocol_step(charge, step, start_time):
    c = charge
    s = step
    t_start = start_time
    p_step = BrewProtocol()
    #p_step.charge = Charge.objects.get(id=c.id)
    p_step.step = s.step
    p_step.title = s.title
    p_step.description = s.description
    p_step.duration = s.duration
    p_step.ingredient = s.ingredient
    if step.amount:
        if step.category.name == "Würzekochung":
            hopping = HopCalculation.objects.filter(charge=c).filter(step=step)
            if hopping:
                step = load_calculated_hopping(step, hopping)
                p_step.amount = step.amount
            else:
                p_step.amount = (s.amount * c.amount) / AMOUNT_FACTOR
        else:
            p_step.amount = (s.amount * c.amount) / AMOUNT_FACTOR
    p_step.tstart = t_start
    p_step.tend = datetime.now()
    return p_step


def storage_delta(charge, step):
    if step.category == "Würzekochung":
        required = step.amount
    else:
        required = charge.amount * step.amount / AMOUNT_FACTOR
    available = Storage.objects.get(id=step.ingredient.id).amount
    delta = available - required
    return delta if delta > 0 else 0
