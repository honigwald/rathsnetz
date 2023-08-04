from django.db import models
from django.conf import settings

from .recipe import Recipe
from .step import RecipeBrewStep
from .hop_calculation import HopCalculation
from .protocol import BrewProtocol, FermentationProtocol

AMOUNT_FACTOR=100
class Charge(models.Model):
    id = models.AutoField(primary_key=True)
    cid = models.CharField(max_length=200, blank=True, null=True)
    brewmaster = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, blank=True, null=True
    )
    production = models.DateTimeField()
    amount = models.IntegerField()
    duration = models.DurationField(blank=True, null=True)
    recipe = models.ForeignKey(Recipe, on_delete=models.DO_NOTHING)
    current_step = models.ForeignKey(
       RecipeBrewStep, on_delete=models.DO_NOTHING, blank=True, null=True
    )
    brew_protocol = models.ForeignKey(BrewProtocol, on_delete=models.CASCADE, blank=True, null=True)
    fermentation_protocol = models.ForeignKey(FermentationProtocol, on_delete=models.CASCADE, blank=True, null=True)
    hopcalculation = models.ManyToManyField(HopCalculation, blank=True)
    brew_factor = models.IntegerField(default=1)
    preps_finished = models.BooleanField(default=False)
    hop_calculation_finished = models.BooleanField(default=False)
    brewing_finished = models.BooleanField(default=False)
    finished = models.BooleanField(default=False)
    ispindel = models.BooleanField(default=False)
    fermentation = models.BooleanField(default=False)
    reached_wort = models.FloatField(blank=True, null=True)
    output = models.FloatField(blank=True, null=True)
    restextract = models.FloatField(blank=True, null=True)

    def __str__(self):
        return str(self.cid)

    # This one don't belong here!
    def get_quantity(self):
        cq = {}
        recipes = Recipe.objects.all()
        for r in recipes:
            total = 0
            charges = Charge.objects.filter(recipe=r).exclude(finished=False)
            for c in charges:
                total = total + c.amount
            cq[r.name] = total
        return cq

    def progress(self):
        s = []
        while self.recipe.steps():
            s.append(step)
            try:
                step = step.next
            except AttributeError:
                step = None

        progress = ((s.index(self.current_step) + 1) / len(s)) * 100

        return int(progress)

    def recipe(self):
        s = []
        step = self.recipe.steps()
        while step:
            if step.ingredient:
                try:
                    hops = HopCalculation.objects.filter(charge=self).filter(step=step)
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
                    step.amount = (step.amount * self.amount) / AMOUNT_FACTOR
                    s.append(step)
            else:
                s.append(step)
            try:
                step = step.next
            except RecipeBrewStep.DoesNotExist:
                step = None
        return s 
    
    def calculate_hops(self):
        self.recipe.h

        ch = HopCalculation(charge=self.id, step)

    id = models.AutoField(primary_key=True)
    charge = models.CharField(max_length=50, default="")
    step = models.ForeignKey(RecipeStep, on_delete=models.DO_NOTHING, blank=True, null=True)
    amount = models.FloatField()
    ibu = models.FloatField()
        return self