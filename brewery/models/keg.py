from django.db import models
from .charge import Charge


class Keg(models.Model):
    id = models.AutoField(primary_key=True)
    STATUS_CHOICES = (
        ("F", "Unverplant"),
        ("E", "Leer"),
        ("S", "Verkauft"),
        ("D", "Defekt"),
    )
    content = models.ForeignKey(
        Charge,
        on_delete=models.SET_NULL,
        blank=True,
        null=True,
        limit_choices_to={"finished": True},
    )
    status = models.CharField(max_length=1, default="F", choices=STATUS_CHOICES)
    notes = models.CharField(max_length=200, blank=True, null=True)
    volume = models.IntegerField()
    filling = models.DateTimeField(blank=True, null=True)

    def __str__(self):
        return "[" + str(self.id) + "] " + str(self.content)

    # This don't belong here!
    def get_beer_in_stock(self):
        bis = {}
        beer = Keg.objects.all().exclude(content=None)
        for keg in beer:
            try:
                bis[keg.content.recipe.name] = keg.volume + bis[keg.content.recipe.name]
            except KeyError:
                bis[keg.content.recipe.name] = keg.volume

        empty = Keg.objects.all().filter(content=None)
        bis["Leer"] = 0
        for keg in empty:
            bis["Leer"] = bis["Leer"] + keg.volume
        return bis
