import logging

from django.db import models
from django.db import transaction
from django.conf import settings
from datetime import datetime

from brewery.models import Recipe
from brewery.models import RecipeBrewStep
from brewery.models import HopCalculation
from brewery.models import Storage
from brewery.models import Unit
from brewery.models import Preparation

from brewery.models import BrewProtocol
from brewery.models import FermentationProtocol
from brewery.models import Hint

from brewery.utils import load_dynamic_bg_image, AMOUNT_FACTOR


from math import exp


class Charge(models.Model):
    id = models.AutoField(primary_key=True)
    cid = models.CharField(max_length=200, blank=True, null=True)
    brewmaster = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.DO_NOTHING, blank=True, null=True
    )
    production = models.DateTimeField()
    amount = models.IntegerField()
    duration = models.DurationField(blank=True, null=True)
    recipe = models.ForeignKey(Recipe, on_delete=models.DO_NOTHING)
    current_step = models.ForeignKey(
        RecipeBrewStep, on_delete=models.DO_NOTHING, blank=True, null=True
    )
    brew_protocol = models.ForeignKey(
        BrewProtocol, on_delete=models.CASCADE, blank=True, null=True
    )
    fermentation_protocol = models.ForeignKey(
        FermentationProtocol, on_delete=models.CASCADE, blank=True, null=True
    )
    # hopcalculation = models.ManyToManyField(HopCalculation, blank=True)
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

    def init(self, recipe, amount, brewmaster, double):
        # Calculate charge ID
        current_year = datetime.now().strftime("%Y")
        yearly_production = (
            Charge.objects.filter(production__contains=current_year + "-").count() + 1
        )
        current_year_month = datetime.now().strftime("%Y%m")
        # Create new charge
        self.cid = current_year_month + "." + str(yearly_production).zfill(2)
        self.production = datetime.now()
        self.recipe = recipe
        self.amount = amount
        self.brewmaster = brewmaster
        self.current_step = self.recipe.head
        if double is True:
            self.brew_factor = 2
        else:
            self.brew_factor = 1
        self.save()

        for prep in self.recipe.preps.all():
            prep = PendingPreparation.objects.create(
                charge=self, preparation=prep, done=False
            )
            logging.debug(prep)
            prep.save()

        # Create brew protocol
        brew_protocol = BrewProtocol(pid=self.cid)
        brew_protocol.save()
        self.brew_protocol = brew_protocol

    def get_progress(self):
        steps = self.recipe.steps()
        if steps is None:
            return 100
        return int((list(steps).index(self.current_step) + 1) / len(steps) * 100)

    def preparations(self):
        self.preps_finished = True
        preps = PendingPreparation.objects.filter(charge=self)
        for prep in preps:
            if prep.done is False:
                self.preps_finished = False
        self.save()
        return preps

    def context(self):
        context = {
            "navi": "brewing",
            "charge": self,
            "image_url": load_dynamic_bg_image(),
            "preps": self.recipe.preps,
            "hg": self.amount * self.recipe.hg / AMOUNT_FACTOR,
            "ng": self.amount * self.recipe.ng / AMOUNT_FACTOR,
            "t_start": datetime.now(),
        }
        if not self.brewing_finished:
            context["recipe"] = self.brew_steps()
            context["step"] = self.current_step
            context["s_next"] = self.current_step.next
            context["progress"] = self.get_progress()
            if self.brew_protocol:
                context["protocol"] = self.brew_protocol.list()
            context["preps"] = None
            hint = Hint.objects.filter(step__id=self.current_step.id)
            context["hint"] = hint if hint.exists() else None

        return context

    def glenn_tinseth_hop(self, hop, ibu, unit, est):
        step_boiltime = self.recipe.boiltime.total_seconds() - est

        # logging.debug("{}(bt) min = {}(total_bt) - {}(progr)".format(
        #    boiltime/60, charge.recipe.boiltime.total_seconds(), progress))

        utilization = 10
        # 10% higher utilization of hop, when pellets are used.
        # Currently we're not distingush between pellets and dolden.
        # Therefore pellet is always true.
        utilization += utilization / 100 * 10 if True else 0

        # 10% higher utilization of hop, when added after 15min.
        utilization += utilization / 100 * 10 if (est / 60) >= 15 else 0

        A = (ibu * self.amount) / (hop.alpha * utilization)
        B = 1.65 * pow(0.000125, (0.004 * self.recipe.wort))
        C = (1 - exp((-0.04) * step_boiltime / 60)) / (4.15)
        """
        logging.debug(
            "Formula_A: {} = ({} * {})/ ({} * {})".format(
                A, ibu, charge.amount, hop.alpha, utilization
            )
        )
        logging.debug(
            "Formula_B: %s = (1.65 * pow(0.000125, (0.004 * %s)))",
            B,
            charge.recipe.wort,
        )
        logging.debug(
            "Formula_C: %s = (1 - exp( (-0.04) * %s /60 )) / 4.15", C, boiltime
        )
        """
        calculated_hop = A / (B * C)

        # units are important!!!
        calculated_hop /= 1000 if hop.unit.name == "kg" else 1

        return round(calculated_hop, 2)

    def glenn_tinseth_ibu(self, hop, amount, unit, est):
        logging.debug(hop)
        boiltime = self.recipe.boiltime.total_seconds() - est
        # units are important!!!
        amount *= 1000 if unit == "kg" else 1

        utilization = 10
        # 10% higher utilization of hop, when pellets are used.
        # Currently we're not distingush between pellets and dolden.
        # Therefore pellet is always true.
        utilization += utilization / 100 * 10 if True else 0

        # 10% higher utilization of hop, when added after 15min.
        utilization += utilization / 100 * 10 if (est / 60) >= 15 else 0

        # logging.debug("{}(bt) min = {}(total_bt) - {}(progr)".format(
        #    boiltime/60, charge.recipe.boiltime.total_seconds(), progress))
        A = (amount * hop.alpha * (utilization)) / self.amount
        B = 1.65 * pow(0.000125, (0.004 * self.recipe.wort))
        C = (1 - exp((-0.04) * boiltime / 60)) / (4.15)
        """
        logging.debug(
            "Formula_A: {} = ({} * {})/ ({} * {})".format(
                A, ibu, charge.amount, hop.alpha, utilization
            )
        )
        logging.debug(
            "Formula_B: %s = (1.65 * pow(0.000125, (0.004 * %s)))",
            B,
            charge.recipe.wort,
        )
        logging.debug(
            "Formula_C: %s = (1 - exp( (-0.04) * %s /60 )) / 4.15", C, boiltime
        )
        """
        ibu = round(A * B * C, 1)

        return ibu

    def calculate_hops(self, renew: bool):
        logging.debug("running")
        if renew:
            # TODO_SIB: Delete old steps!
            hops = HopCalculation.objects.filter(charge_id=self.cid)
            for hop in hops:
                hop.delete()
            self.hop_calculation_finished = False
            return

        if self.hop_calculation_finished:
            return

        # TODO_SIB: check for reached overall IBU. It could be, that recipe and steps don't match
        calculated_substitutes = list()
        for step in self.recipe.steps_with_hops():
            scaled_amount = self.amount * step.amount / AMOUNT_FACTOR
            # calculate IBU of current step, which is required by the recipe
            est = self.recipe.est_during_boiltime(step)
            required_ibu = self.glenn_tinseth_ibu(
                step.ingredient, scaled_amount, step.unit.name, est
            )
            remaining_ibu = required_ibu

            hops = Storage.objects.filter(name=step.ingredient.name).order_by("-amount")
            for hop in hops:
                if hop.amount == 0:
                    continue
                # Calculate possible IBU with available hop in stock
                possible_ibu = self.glenn_tinseth_ibu(
                    hop, hop.amount, hop.unit.name, est
                )
                if possible_ibu > remaining_ibu:
                    calc_hop_amount = self.glenn_tinseth_hop(
                        hop, remaining_ibu, hop.unit, est
                    )
                    possible_ibu = self.glenn_tinseth_ibu(
                        hop, calc_hop_amount, hop.unit.name, est
                    )
                else:
                    calc_hop_amount = self.glenn_tinseth_hop(
                        hop, possible_ibu, hop.unit, est
                    )

                remaining_ibu -= possible_ibu

                # Create and save substitute
                substitute = HopCalculation(
                    charge_id=self.cid,
                    step=step,
                    ingredient=hop,
                    amount=calc_hop_amount,
                    unit=hop.unit,
                    ibu=possible_ibu,
                )
                substitute.save()
                calculated_substitutes.append(substitute)

                if remaining_ibu <= 0:
                    break

        logging.debug("calculate_hops: %s", calculated_substitutes)
        return calculated_substitutes

    def brew_steps(self):
        logging.debug("brew_steps")
        s = []

        if self.current_step == self.recipe.tail:
            return s

        for step in list(self.recipe.steps())[self.current_step.pos + 1 :]:
            if step.ingredient:
                # try:
                #    hops = HopCalculation.objects.filter(charge=self).filter(step=step)
                # except HopCalculation.DoesNotExist:
                #    hops = None
                hops = []
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
        logging.debug(s)
        return s

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

    def get_missing_ingredients(self):
        missing = list()
        for step in self.recipe.steps():
            if step.amount:
                required = self.amount * step.amount / AMOUNT_FACTOR
                # TODO_SIB: unit-check!
                in_stock = Storage.objects.get(id=step.ingredient.id).amount
                remaining = in_stock - required

                if remaining < 0:
                    missing.append(step.ingredient)
        return missing

    @transaction.atomic
    def calculate_ingredients(self):
        ingredients = {}
        progress = 0
        savepoint = transaction.savepoint()
        details = []
        calculated_hops = list()
        for s in self.recipe.steps():
            if s.ingredient:
                if s.duration and s.ingredient.type.name == "Hopfen":
                    progress += s.duration.total_seconds()
                required_amount = self.amount * s.amount / AMOUNT_FACTOR
                # Calculate hops
                if s.ingredient.type.name == "Hopfen":
                    if not self.hop_calculation_finished:
                        calculated_hops = self.calculate_hops(False)

                # Calculate other ingredients
                else:
                    details.append(s.ingredient.name)
                    details.append(required_amount)
                    details.append(s.unit.name)

                    if s.ingredient.type in ingredients:
                        tmp = ingredients[s.ingredient.type]
                        tmp.append(details)
                        ingredients[s.ingredient.type] = details
                    else:
                        tmp = list()
                        tmp.append(details)
                        ingredients[s.ingredient.type] = tmp
                    details = []

        ingredients["Wasser"] = [
            ["Hauptguss", self.recipe.hg * self.amount / AMOUNT_FACTOR, "Liter"],
            ["Nachguss", self.recipe.ng * self.amount / AMOUNT_FACTOR, "Liter"],
        ]

        transaction.savepoint_rollback(savepoint)
        if self.hop_calculation_finished is False and calculated_hops != {}:
            for hop in calculated_hops:
                hop.save()
        self.hop_calculation_finished = True
        self.save()

        return ingredients

    def get_calculated_hops(self):
        total_ibu = hops = None
        if self.hop_calculation_finished is True:
            total_ibu = 0
            hops = HopCalculation.objects.filter(charge_id=self.cid)
            for item in hops:
                if item.unit.name == "kg":
                    item.unit = Unit.objects.get(name="g")
                    item.amount *= 1000
                    item.save()

                total_ibu += item.ibu
        return total_ibu, hops

    def processing(self, comment, tstart):
        current_step = self.current_step
        # Update storage
        if current_step.amount:
            # TODO_SIB: update storage
            logging.debug("remove amount from storage")

        # Save step to protocol
        if not self.brew_protocol:
            brew_protocol = BrewProtocol(
                rname=self.recipe.name, pid=self.cid, head=None, tail=None
            )
            brew_protocol.save()
            self.brew_protocol = brew_protocol

        self.brew_protocol.add_step(
            current_step=current_step, comment=comment, tstart=tstart
        )

        # Check if we've reached the last brewing step
        if current_step.next is None:
            self.brewing_finished = True
        else:
            self.current_step = current_step.next
        self.save()

        """
        p_step = protocol_step(c, step, t_start)
        p_step.comment = p_form.cleaned_data["comment"]
        p_step.save()
        # Update storage
        if step.amount:
            logging.debug(
                "brewing: calculate remaining amount of %s in stock.",
                step.ingredient,
            )
            item_in_stock = Storage.objects.get(id=step.ingredient.id)
            item_in_stock.amount = storage_delta(c, step)
            item_in_stock.save()
            # delete first element of hop calculations
            if hopping:
                hopping = HopCalculation.objects.filter(charge=c).filter(
                    step=step
                )
                logging.debug(
                    "brewing: delete first elemet (%s) of hop calculation's (%s).",
                    hopping[0].ingredient,
                    hopping,
                )
                hopping[0].delete()

        # Check if there still is hopping neccassary
        if not hopping:
            # Check if there is a next step
            try:
                step = step.next
                logging.debug("brewing: get next step: %s", step)
                step.amount = (
                    (step.amount * c.amount) / AMOUNT_FACTOR
                    if step.amount
                    else step.amount
                )

                # Check if current step contains hop, then load it's calculation
                if step.category.name == "Würzekochung":
                    hopping = HopCalculation.objects.filter(charge=c).filter(
                        step=step
                    )
                    # if hopping:
                    #    step = load_calculated_hopping(step, hopping)
                    logging.debug(
                        "brewing: hopping for %s is %s", step, hopping.count()
                    )

                cur_step_succ = get_next_step(c, step)
                logging.debug(
                    "brewing: get successor of %s. Successor: %s",
                    step,
                    cur_step_succ,
                )

                context["charge"] = c
                context["t_start"] = datetime.now()
                context["step"] = step
                context["s_next"] = cur_step_succ
                context["hint"] = Hint.objects.filter(step__id=step.id)
                context["protocol"] = RecipeProtocol.objects.filter(charge=cid)
                context["form"] = BrewingProtocol()
                context["recipe"] = get_steps(c.recipe, c, c.amount)
                context["hg"] = c.amount * c.recipe.hg / AMOUNT_FACTOR
                context["ng"] = c.amount * c.recipe.ng / AMOUNT_FACTOR
                context["progress"] = c.get_progress()
                c.current_step = step
                c.save()
                return render(request, "brewery/brewing.html", context)
            # Brewing: Finished
            except AttributeError:
                logging.debug(
                    "brewing: brewing process finished. continue with fermentation"
                )
                # Calculate overall duration time
                c.duration = datetime.now() - c.production.replace(tzinfo=None)
                c.brewing_finished = True
                c.save()
                context["charge"] = c
                context["protocol"] = RecipeProtocol.objects.filter(charge=cid)
                return HttpResponseRedirect(
                    reverse("fermentation", kwargs={"cid": c.id})
                )
        else:
            logging.debug(
                "brewing: Left hops for this step: %s", hopping.count()
            )

            # step = load_calculated_hopping(step, hopping)
            cur_step_succ = get_next_step(c, step)
            logging.debug(
                "brewing: get successor of %s. Successor: %s",
                step,
                cur_step_succ,
            )

            context["charge"] = c
            context["t_start"] = datetime.now()
            context["step"] = step
            context["s_next"] = cur_step_succ
            context["hint"] = Hint.objects.filter(step__id=step.id)
            context["protocol"] = RecipeProtocol.objects.filter(charge=cid)
            context["form"] = BrewingProtocol()
            context["recipe"] = get_steps(c.recipe, c, c.amount)
            context["hg"] = c.amount * c.recipe.hg / AMOUNT_FACTOR
            context["ng"] = c.amount * c.recipe.ng / AMOUNT_FACTOR
            context["progress"] = c.get_progress()
            context["navi"] = "brewing"
            context["image_url"] = load_dynamic_bg_image()
            c.current_step = step
            c.save()
            return render(request, "brewery/brewing.html", context)
        """

    def init_fermentation(self):
        if not self.fermentation_protocol:
            self.fermentation_protocol = FermentationProtocol()
            self.fermentation_protocol.save()
            self.save()


""" ---------- PENDING PREPARATIONS ---------- """


class PendingPreparation(models.Model):
    id = models.AutoField(primary_key=True)
    charge = models.ForeignKey(Charge, on_delete=models.CASCADE)
    preparation = models.ForeignKey(Preparation, on_delete=models.DO_NOTHING)
    done = models.BooleanField()

    def __str__(self):
        return "[" + self.charge.cid + "] " + str(self.preparation.short)
