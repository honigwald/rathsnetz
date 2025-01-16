from django.db import models
from .step import RecipeBrewStep


class Hint(models.Model):
    id = models.AutoField(primary_key=True)
    hint = models.CharField(max_length=50)
    step = models.ManyToManyField(RecipeBrewStep)

    def __str__(self):
        return self.hint
