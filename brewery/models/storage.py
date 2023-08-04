from django.db import models
from django.core.validators import MinValueValidator
from .type import Type
from .unit import Unit


class Storage(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=200)
    type = models.ForeignKey(Type, on_delete=models.DO_NOTHING)
    unit = models.ForeignKey(Unit, on_delete=models.DO_NOTHING)
    amount = models.FloatField(validators=[MinValueValidator(0.0)])
    threshold = models.BooleanField(default=False)
    warning = models.IntegerField(default=-1)
    danger = models.IntegerField(default=-1)
    alpha = models.FloatField(default=None, blank=True, null=True)

    def __str__(self):
        if self.alpha:
            return self.name + " \u03B1=" + str(self.alpha) + "%"
        else:
            return self.name
