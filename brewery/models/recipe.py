from django.db import models
from django.utils import timezone
from django.conf import settings
from .step import RecipeBrewStep
from .preparation import Preparation


class Recipe(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=25)
    creation = models.DateTimeField(default=timezone.now)
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING, blank=True, null=True
    )
    hg = models.FloatField()
    ng = models.FloatField()
    head = models.ForeignKey(RecipeBrewStep, on_delete=models.CASCADE, blank=True, null=True)
    wort = models.FloatField()
    ibu = models.FloatField()
    boiltime = models.DurationField()
    preps = models.ManyToManyField(Preparation, blank=True)

    def __str__(self):
        return self.name
    
    def preparation(self):
        return Preparation.objects.filter(recipe=self)
    
    def steps(self):
        return self.head.list()
    
    def hop_steps(self):
        los = []
        step = self.head
        while step:
            if step.ingredient.type.name == "Hopfen":
                los.append(step)
            try:
                step = step.next
            except RecipeBrewStep.DoesNotExist:
                step = None
        return los
    