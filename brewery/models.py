from django.db import models
from django.utils import timezone
from django.conf import settings


class Unit(models.Model):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name


class Type(models.Model):
    name = models.CharField(max_length=200)

    def __str__(self):
        return self.name


class Storage(models.Model):
    name = models.CharField(max_length=200)
    type = models.ForeignKey(Type, on_delete=models.CASCADE)
    unit = models.ForeignKey(Unit, on_delete=models.CASCADE)
    amount = models.FloatField()
    threshold = models.BooleanField(default=False)
    warning = models.IntegerField(default=-1)
    danger = models.IntegerField(default=-1)

    def __str__(self):
        return self.name


class Recipe(models.Model):
    name = models.CharField(max_length=25)
    creation = models.DateTimeField(default=timezone.now)
    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, blank=True, null=True)
    hg = models.FloatField()
    ng = models.FloatField()
    first = models.IntegerField(default=None, blank=True, null=True)

    def __str__(self):
        return self.name


class Step(models.Model):
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE)
    prev = models.OneToOneField('self', null=True, blank=True, related_name="next", on_delete=models.DO_NOTHING)
    step = models.IntegerField(blank=True, null=True)
    title = models.CharField(max_length=50)
    description = models.CharField(max_length=200)
    duration = models.DurationField(blank=True, null=True)
    ingredient = models.ForeignKey(Storage, on_delete=models.CASCADE, blank=True, null=True)
    amount = models.FloatField(blank=True, null=True)

    def __str__(self):
        return "[" + str(self.recipe) + "] " + str(self.step) + ". " + str(self.title)


class Charge(models.Model):
    cid = models.CharField(max_length=200, blank=True, null=True)
    recipe = models.ForeignKey(Recipe, on_delete=models.CASCADE)
    amount = models.IntegerField()
    production = models.DateTimeField()
    duration = models.DurationField(blank=True, null=True)
    brewmaster = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, blank=True, null=True)
    preps_finished = models.BooleanField(default=False)
    brewing_finished = models.BooleanField(default=False)
    finished = models.BooleanField(default=False)
    ispindel = models.BooleanField(default=False)
    fermentation = models.BooleanField(default=False)
    current_step = models.ForeignKey(Step, on_delete=models.DO_NOTHING, blank=True, null=True)

    def __str__(self):
        return str(self.cid)


class Keg(models.Model):
    STATUS_CHOICES = (
        ('F', 'Unverplant'),
        ('E', 'Leer'),
        ('S', 'Verkauft'),
        ('D', 'Defekt'),
    )
    content = models.ForeignKey(Charge, on_delete=models.CASCADE, blank=True, null=True, limit_choices_to={'finished': True})
    status = models.CharField(max_length=1, default='F', choices=STATUS_CHOICES)
    notes = models.CharField(max_length=200, blank=True, null=True)
    volume = models.IntegerField()
    filling = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return "[" + str(self.id) + "] " + str(self.content)


class FermentationProtocol(models.Model):
    charge = models.ForeignKey(Charge, on_delete=models.CASCADE)
    step = models.IntegerField()
    temperature = models.FloatField()
    plato = models.FloatField()
    date = models.DateTimeField()

    def __str__(self):
        return "[" + str(self.charge) + "] " + str(self.step)


class Hint(models.Model):
    hint = models.CharField(max_length=50)
    step = models.ManyToManyField(Step)

    def __str__(self):
        return self.hint


class Preparation(models.Model):
    short = models.CharField(max_length=20)
    detail = models.CharField(max_length=600)
    recipe = models.ManyToManyField(Recipe, blank=True)
    
    def __str__(self):
        return self.short


class RecipeProtocol(models.Model):
    charge = models.ForeignKey(Charge, on_delete=models.CASCADE)
    step = models.IntegerField()
    title = models.CharField(max_length=50)
    description = models.CharField(max_length=200)
    duration = models.DurationField(blank=True, null=True)
    ingredient = models.CharField(max_length=200, blank=True, null=True)
    amount = models.FloatField(blank=True, null=True)
    tstart = models.TimeField()
    tend = models.TimeField()
    comment = models.CharField(max_length=200, blank=True, null=True)

    def __str__(self):
        return str(self.charge) + "." + str(self.step)


class PreparationProtocol(models.Model):
    charge = models.ForeignKey(Charge, on_delete=models.CASCADE)
    preparation = models.ForeignKey(Preparation, on_delete=models.CASCADE)
    check = models.BooleanField()

    def __str__(self):
        return str(self.charge.cid) + "_" + str(self.preparation.short)