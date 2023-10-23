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
    head = models.ForeignKey(
        RecipeBrewStep, on_delete=models.CASCADE, blank=True, null=True
    )
    wort = models.FloatField()
    ibu = models.FloatField()
    boiltime = models.DurationField()
    preps = models.ManyToManyField(Preparation, blank=True)

    def __str__(self):
        return self.name

    def preparations(self):
        return self.preps
        # return Preparation.objects.filter(recipe=self)

    def steps(self):
        return self.head.dict().values()

    def hop_steps(self):
        los = []
        for step in self.steps():
            if step.ingredient.type.name == "Hopfen":
                los.append(step)
        return los

    def est_during_boiltime(self, curr_step):
        est = 0
        for step in self.steps():
            if curr_step.duration and curr_step.category.name == "Würzekochung":
                est += step.duration.total_seconds()
            if step == curr_step:
                return est

    def add_step(self, step):
        if step.prev is None:
            self.head.prev = step
            self.head = step
        else:
            step.prev.next.prev = step

    def del_step(self, step):
        if step.prev is None:
            step.next = self.head
        else:
            step.prev.next = step.next

        # TODO delete step

    def step_by_id(self, id):
        return self.head.dict().get(id)
