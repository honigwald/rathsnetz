from django.db import models
from django.utils import timezone
from django.conf import settings

# Create your models here.
class Recipe(models.Model):
    name = models.CharField(max_length=200)
    creation = models.DateTimeField(default=timezone.now)

    def __str__(self):
        return self.name


class Charge(models.Model):
    cid = models.CharField(max_length=200, blank=True, null=True)
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE)
    amount = models.IntegerField()
    production = models.DateTimeField()
    duration = models.DurationField(blank=True, null=True)
    brewmaster = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, blank=True, null=True)

    def __str__(self):
        return str(self.cid)


class BeerStorage(models.Model):
    keg_nr = models.AutoField(primary_key=True)
    content = models.ForeignKey(Charge, on_delete=models.CASCADE, blank=True, null=True)
    status = models.CharField(max_length=200, default='empty')
    volume = models.IntegerField()
    filling = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return "[" + str(self.keg_nr) + "] " + str(self.content)


class Fermentation(models.Model):
    charge = models.ForeignKey(Charge, on_delete=models.CASCADE)
    temperature = models.FloatField()
    fermentation = models.FloatField()
    date = models.DateTimeField()

    def __str__(self):
        return "[" + str(self.charge) + "] "


class Unit(models.Model):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name


class Type(models.Model):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name


class IngredientStorage(models.Model):
    name = models.CharField(max_length=200)
    type = models.ForeignKey(Type, on_delete=models.CASCADE)
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE)
    amount = models.FloatField()

    def __str__(self):
        return self.name


class Step(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE)
    step = models.IntegerField()
    title = models.CharField(max_length=50)
    description = models.CharField(max_length=200)
    duration = models.DurationField(blank=True, null=True)
    ingredient = models.ForeignKey(IngredientStorage, on_delete=models.CASCADE, blank=True, null=True)
    amount = models.FloatField(blank=True, null=True)

    def __str__(self):
        return "[" + str(self.recipe) + "] " + str(self.step) + ". " + str(self.title)


class Protocol(models.Model):
    step = models.IntegerField()
    charge = models.ForeignKey(Charge, on_delete=models.CASCADE)
    title = models.CharField(max_length=50)
    description = models.CharField(max_length=200)
    duration = models.DurationField(blank=True, null=True)
    ingredient = models.CharField(max_length=200, blank=True, null=True)
    amount = models.FloatField(blank=True, null=True)
    tstart = models.TimeField()
    tend = models.TimeField()
    comment = models.CharField(max_length=200)

    def __str__(self):
        return str(self.charge) + "." + str(self.step)
