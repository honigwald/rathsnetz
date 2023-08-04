from django.db import models
from .storage import Storage
from .unit import Unit
from .category import Category


class Step(models.Model):
    id = models.AutoField(primary_key=True)
    step_number = models.IntegerField(blank=True, null=True)
    prev = models.OneToOneField(
        "self", null=True, blank=True, related_name="next", on_delete=models.DO_NOTHING
    )
    class Meta:
        abstract = True

    def list(self):
        los = []
        step = self
        while step:
            los.append(step)
            try:
                step = step.next
            except Step.DoesNotExist:
                step = None
        return los 

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
    

class ProtocolBrewStep(BrewStep):
    tstart = models.TimeField()
    tend = models.TimeField()
    comment = models.CharField(max_length=200, blank=True, null=True)

    def __str__(self):
        return "[]"

class ProtocolFermentationStep(Step):
    temperature = models.FloatField()
    plato = models.FloatField()
    date = models.DateTimeField()

    def __str__(self):
        return "[]"
