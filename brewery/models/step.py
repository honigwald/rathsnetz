from django.db import models
from .storage import Storage
from .unit import Unit
from .category import Category
from .hop_calculation import HopCalculation


class Step(models.Model):
    id = models.AutoField(primary_key=True)
    no = models.IntegerField(blank=True, null=True)
    prev = models.OneToOneField(
        "self", null=True, blank=True, related_name="next", on_delete=models.DO_NOTHING
    )

    class Meta:
        abstract = True

    def dict(self):
        dos = {}
        step = self
        while step:
            dos[step.id] = step
            if hasattr(step, "next"):
                step = step.next
            else:
                return dos


class BrewStep(Step):
    title = models.CharField(max_length=50, default="")
    description = models.CharField(max_length=200, default="")
    ingredient = models.ForeignKey(
        Storage, on_delete=models.CASCADE, blank=True, null=True
    )
    amount = models.FloatField(blank=True, null=True)
    unit = models.ForeignKey(Unit, on_delete=models.DO_NOTHING, blank=True, null=True)

    class Meta:
        abstract = True


class RecipeBrewStep(BrewStep):
    duration = models.DurationField(blank=True, null=True)
    category = models.ForeignKey(Category, on_delete=models.DO_NOTHING)
    ibu = models.FloatField(blank=True, null=True)

    def __str__(self):
        return "[" + str(self.id) + "] " + str(self.step) + ". " + str(self.title)

    def calculate_hopping(self, charge):
        hc = HopCalculation(charge=charge, step=self)
        hc.calculate()

    def has_substitue(self, charge):
        return HopCalculation.objects.filter(charge=charge).filter(step=self)

    # def load_calculated_hopping(step, hopping):
    #    logging.debug("load_calculated_hopping")
    #    step.amount = hopping[0].amount
    #    step.ingredient = hopping[0].ingredient
    #    step.description = "Hopfenrechner: " + str(hopping[0].ibu) + " IBU"
    #    return step


class BrewProtocolStep(BrewStep):
    tstart = models.TimeField()
    tend = models.TimeField()
    comment = models.CharField(max_length=200, blank=True, null=True)

    def __str__(self):
        return "[]"


class FermentationProtocolStep(Step):
    temperature = models.FloatField()
    plato = models.FloatField()
    date = models.DateTimeField()

    def __str__(self):
        return "[]"
