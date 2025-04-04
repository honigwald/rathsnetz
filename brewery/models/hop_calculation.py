import logging

from django.db import models


from brewery.models import RecipeBrewStep
from brewery.models import Storage
from brewery.models import Unit


class HopCalculation(models.Model):
    id = models.AutoField(primary_key=True)
    charge_id = models.CharField(max_length=50, default="")
    # models.ManyToOneField()

    step = models.ForeignKey(
        RecipeBrewStep, on_delete=models.DO_NOTHING, blank=True, null=True
    )
    ingredient = models.ForeignKey(
        Storage, on_delete=models.DO_NOTHING, blank=True, null=True
    )
    amount = models.FloatField()
    ibu = models.FloatField()
    unit = models.ForeignKey(Unit, on_delete=models.DO_NOTHING, null=True)

    def __str__(self):
        return self.charge_id + "_" + str(self.step)

    def load_calculated_hopping(step, hopping):
        logging.debug("load_calculated_hopping")
        step.amount = hopping[0].amount
        step.ingredient = hopping[0].ingredient
        step.description = "Hopfenrechner: " + str(hopping[0].ibu) + " IBU"
        return step


"""

# HELPER FUNCTION
def get_steps(rid, charge, amount):
    try:
        step = RecipeBrewStep.objects.get(pk=rid.first)
    except RecipeBrewStep.DoesNotExist:
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
                        add_step = RecipeBrewStep.objects.get(id=step.id)
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
            next_step = RecipeBrewStep.objects.get(id=step.id)
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
    except RecipeBrewStep.DoesNotExist:
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



"""
