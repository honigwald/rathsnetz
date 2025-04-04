import logging
import sys

from django.db import models
from django.utils import timezone
from django.conf import settings

from brewery.models import Preparation
from brewery.models import RecipeBrewStep

from brewery.utils import load_dynamic_bg_image

logging.basicConfig(stream=sys.stdout, level=logging.DEBUG)


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
        RecipeBrewStep, related_name="recipe_head", on_delete=models.SET_NULL, null=True
    )
    tail = models.ForeignKey(
        RecipeBrewStep, related_name="recipe_tail", on_delete=models.SET_NULL, null=True
    )
    wort = models.FloatField()
    ibu = models.FloatField()
    boiltime = models.DurationField()
    preps = models.ManyToManyField(Preparation, blank=True)

    def __str__(self):
        return self.name

    def preparations(self):
        return self.preps.values()
        # return Preparation.objects.filter(recipe=self)

    def add_preparation(self, prep: Preparation):
        self.preps.add(prep)

    def steps(self):
        if self.head is not None:
            return self.head.dict().values()
        else:
            return None

    def steps_with_hops(self):
        hopsteps = []
        for step in self.steps():
            if step.ingredient and step.ingredient.type.name == "Hopfen":
                hopsteps.append(step)
        logging.debug(hopsteps)
        return hopsteps

    def est_during_boiltime(self, curr_step):
        est = 0
        for step in self.steps():
            if step.duration and step.category.name == "Würzekochung":
                est += step.duration.total_seconds()
            if step == curr_step:
                return est

    def step_by_id(self, sid: int):
        return self.head.dict().get(sid)

    def update_step_number(self):
        self.refresh_from_db()
        i = 1
        for s in self.steps():
            logging.debug("update_step_number(): [%s] %s -> %s", s, s.pos, i)
            s.pos = i
            s.rname = self.name # ensure recipe name is set
            s.save()
            i += 1

    def query(self):
        return RecipeBrewStep.objects.filter(rname=self.name)

    def add_to_front(self, step: RecipeBrewStep):
        if step == self.head:
            return

        if step == self.tail:
            self.tail = step.previous
            self.save()

        step.unlink_from_list()

        if self.head is None:
            self.head = step
            self.tail = step
        else:
            self.refresh_from_db()
            step.link_between(None, self.head)
            self.head = step

        step.recipe_name(self.name)
        step.save()
        self.save()

    def add_to_end(self, step: RecipeBrewStep):
        if step == self.tail:
            return

        if step == self.head:
            self.head = step.next
            self.save()

        step.unlink_from_list()

        if self.tail is None:
            self.head = step
            self.tail = step
        else:
            self.refresh_from_db()
            step.link_between(self.tail, None)
            self.tail = step

        step.recipe_name(self.name)
        step.save()
        self.save()

    def add_in_between(self, predecessor: RecipeBrewStep, step: RecipeBrewStep):
        if predecessor is None:
            return

        if step == predecessor.next:
            return

        if step == self.head:
            self.head = step.next
            self.head.previous = None
            self.save()
        if step == self.tail:
            self.tail = step.previous
            self.save()
            self.refresh_from_db()
            self.tail.next = None
            self.save()

        step.unlink_from_list()
        predecessor.refresh_from_db()
        step.link_between(predecessor, predecessor.next)
        step.recipe_name(self.name)
        step.save()

    def context(self):
        context = {}
        context["recipe"] = self
        context["steps"] = self.steps()
        context["preparation"] = self.preparations()
        context["navi"] = "recipe"
        context["image_url"] = load_dynamic_bg_image()

        return context
