import logging
import sys
from django.db import models

from brewery.models import Storage
from brewery.models import Unit
from brewery.models import Category

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)


class Step(models.Model):
    id = models.AutoField(primary_key=True)
    pos = models.IntegerField(blank=True, null=True)
    rname = models.CharField(max_length=25, blank=True, null=True)
    previous = models.ForeignKey(
        "self",
        related_name="next_step",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )
    next = models.ForeignKey(
        "self",
        related_name="previous_step",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
    )

    class Meta:
        abstract = True

    def dict(self):
        dos = {}
        step = self
        while step:
            dos[step.id] = step
            step = step.next
        return dos

    def get_predecessor(self):
        if self.previous:
            return self.previous
        else:
            return None

    def unlink_from_list(self):
        # unlink from pred- and successor
        if self.next and self.previous:
            self.next.previous = self.previous
            self.next.save()
            self.previous.next = self.next
            self.previous.save()

        # unlink from successor (current step is head)
        elif self.next:
            self.next.previous = None
            self.next.save()

        # unlink from predeccessor (step is tail)
        elif self.previous:
            self.previous.next = None
            self.previous.save()

        self.next = None
        self.previous = None
        self.save()

    def link_between(self, prev, succ):
        if prev:
            self.previous = prev
            prev.next = self
            prev.save()
        if succ:
            self.next = succ
            succ.previous = self
            succ.save()
        self.save()

    def recipe_name(self, name):
        self.rname = name
        self.save()


class BrewStep(Step):
    title = models.CharField(max_length=50, default="")
    description = models.CharField(max_length=200, default="")
    amount = models.FloatField(blank=True, null=True)
    unit = models.ForeignKey(Unit, on_delete=models.DO_NOTHING, blank=True, null=True)
    duration = models.DurationField(blank=True, null=True)

    class Meta:
        abstract = True


class RecipeBrewStep(BrewStep):
    category = models.ForeignKey(Category, on_delete=models.DO_NOTHING)
    ibu = models.FloatField(blank=True, null=True)
    ingredient = models.ForeignKey(
        Storage, on_delete=models.DO_NOTHING, blank=True, null=True
    )

    def __str__(self):
        return "[" + str(self.rname) + "] " + str(self.pos) + ". " + str(self.title)

    # def calculate_hopping(self, charge):
    # hc = HopCalculation(charge=charge, step=self)
    # hc.calculate()

    # def has_substitue(self, charge):
    # return HopCalculation.objects.filter(charge=charge).filter(step=self)


class BrewProtocolStep(BrewStep):
    tstart = models.TimeField()
    tend = models.TimeField()
    ingredient = models.CharField(max_length=200, blank=True, null=True)
    comment = models.CharField(max_length=200, blank=True, null=True)

    def __str__(self):
        return "[" + str(self.rname) + "] " + str(self.pos) + ". " + str(self.title)


class FermentationProtocolStep(Step):
    temperature = models.FloatField()
    plato = models.FloatField()
    date = models.DateTimeField()

    def __str__(self):
        return str(self.id)
