import locale
import logging
from base64 import urlsafe_b64encode as b64e, urlsafe_b64decode as b64d
from datetime import datetime

# Django imports
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils import timezone

# from django.http import FileResponse
import plotly.graph_objects as go
from plotly.offline import plot

# Local imports (custom modules)
from brewery.models import Charge
from brewery.models import Recipe


# from .models.step import RecipeBrewStep
from .models.keg import Keg
from brewery.models import BrewProtocol, FermentationProtocol  # , PreparationProtocol
from .models.beer_output import BeerOutput
from .models.storage import Storage
from .models.account import Account

from brewery.utils import load_dynamic_bg_image, AMOUNT_FACTOR


# from .protocol import processing_pdf
from .ispindel import save_plot, get_plot

from .forms import (
    EditKegContent,
    BrewingProtocol,
    PendingPreparationForm,
    BrewingCharge,
    FermentationProtocolForm,
    FinishFermentationForm,
    KegSelectForm,
    SelectPreparation,
    EditRecipe,
    InitFermentationForm,
    AddRecipe,
    StepForm,
    StepPredecessorForm,
    StorageAddItem,
)

# Custom configuration
# Set locale for currency formatting (German in this case)
locale.setlocale(locale.LC_ALL, "de_DE.UTF-8")

# Set up logging configurations
# logging.basicConfig(level=logging.DEBUG, stream=sys.stdout)
# logging.basicConfig(stream=sys.stdout)
# logging.basicConfig(level=logging.DEBUG)
# log = logging.basicConfig(stream=sys.stdout, encoding='utf-8', level=logging.DEBUG)

# End of configuration


def index(request):
    logging.debug("index")
    context = {"navi": "overview", "image_url": load_dynamic_bg_image()}
    return render(request, "brewery/index.html", context)


@login_required
def analyse(request):
    logging.warning("analyse: running now!")
    config = {"displayModeBar": False}
    # BIER TOTAL
    c = Charge()
    cq = c.get_quantity()
    key = []
    value = []
    data = []
    for k, v in cq.items():
        key.append(k)
        value.append(v)
        data.append(go.Bar(name=k, x=[k], y=[v]))
    logging.debug("analyse: %s", data)

    cq_fig = go.Figure(data=data)
    cq_fig.update_layout(
        title="Total: Biermengen",
        xaxis_tickfont_size=14,
        yaxis=dict(
            title="Menge [Liter]",
            titlefont_size=16,
            tickfont_size=14,
        ),
        legend=dict(
            xanchor="right",
            y=1.0,
            bgcolor="rgba(255, 255, 255, 0)",
            bordercolor="rgba(255, 255, 255, 0)",
        ),
        barmode="group",
        bargap=0.3,
        xaxis={"categoryorder": "total descending"},
    )
    cq_plt = plot(cq_fig, output_type="div", config=config)

    # BIER IM AUGE
    k = Keg()
    bis = k.get_beer_in_stock()
    key.clear()
    value.clear()
    for k, v in bis.items():
        key.append(k)
        value.append(v)

    trace = go.Pie(labels=key, values=value)
    data = [trace]
    bis_fig = go.Figure(data=data)
    bis_fig.update_traces(textinfo="value", hole=0.4)
    bis_fig.update_layout(title="Lager: Bier im Auge")
    bis_plt = plot(bis_fig, output_type="div", config=config)

    # BIER BALANCE
    bo = BeerOutput()
    bb_data = bo.get_balance()
    bb_fig = go.Figure(
        go.Waterfall(
            name="20",
            orientation="v",
            # measure = ["relative", "relative", "total", "relative", "relative", "total"],
            x=bb_data[0],
            # textposition = "inside",
            # text = ["+60", "+80", "", "-40", "-20", "Total"],
            totals={
                "marker": {
                    "color": "deep sky blue",
                    "line": {"color": "blue", "width": 3},
                }
            },
            y=bb_data[1],
            connector={"line": {"color": "rgb(63, 63, 63)"}},
        )
    )

    bb_fig.update_layout(title="Bier.Balance: Eingang/Ausgang", waterfallgap=0.1)
    bb_plt = plot(bb_fig, output_type="div", config=config)

    # GELD BALANCE
    ac = Account()
    ab_data = ac.get_balance()
    ab_fig = go.Figure(
        go.Waterfall(
            name="20",
            orientation="v",
            # measure = ["relative", "relative", "total", "relative", "relative", "total"],
            x=ab_data[0],
            # textposition = "inside",
            # text = ["+60", "+80", "", "-40", "-20", "Total"],
            totals={
                "marker": {
                    "color": "deep sky blue",
                    "line": {"color": "blue", "width": 3},
                }
            },
            y=ab_data[1],
            connector={"line": {"color": "rgb(63, 63, 63)"}},
        )
    )

    ab_fig.update_layout(title="Geld.Balance: Eingang/Ausgang", waterfallgap=0.1)
    ab_plt = plot(ab_fig, output_type="div", config=config)

    context = {
        "navi": "analyse",
        "image_url": load_dynamic_bg_image(),
        "cq_plt": cq_plt,
        "bis_plt": bis_plt,
        "bb_plt": bb_plt,
        "ab_plt": ab_plt,
    }
    return render(request, "brewery/analyse.html", context)


@login_required
def brewing_overview(request):
    c = Charge.objects.filter(finished=True)
    active = Charge.objects.filter(finished=False)
    context = {
        "charge": c,
        "active": active,
        "navi": "brewing",
        "image_url": load_dynamic_bg_image(),
    }
    return render(request, "brewery/brewing_overview.html", context)


@login_required
def brewing(request, cid):
    c = get_object_or_404(Charge, pk=cid)
    context = c.context()
    context["form"] = BrewingProtocol()

    # Charge finished: Goto Protocol
    if c.finished:
        return HttpResponseRedirect(reverse("protocol", kwargs={"cid": c.id}))

    # Preparation and Brewing finished: Goto Fermentation
    elif c.preps_finished and c.brewing_finished:
        c.init_fermentation()
        return HttpResponseRedirect(reverse("fermentation", kwargs={"cid": c.id}))

    # Brew is ongoing: restore session
    elif c.preps_finished and not request.POST:
        logging.debug("brewing: Restoring session [Finished: Preparations]")
        return render(request, "brewery/brewing.html", context)

    # Create or continue a new charge
    else:
        # Preparations: save session
        if request.POST.get("preps_save"):
            preps_form = [
                PendingPreparationForm(request.POST, prefix=str(item), instance=item)
                for item in c.preparations()
            ]
            for pf in preps_form:
                if pf.is_valid():
                    pf.save()
            return HttpResponseRedirect(reverse("brewing_overview"))

        # Preparations: validate preparations and start brewing
        if request.POST.get("preps_next"):
            preps_form = [
                PendingPreparationForm(request.POST, prefix=str(item), instance=item)
                for item in c.preparations()
            ]
            for pf in preps_form:
                if pf.is_valid():
                    pf.save()
                    c.preparations()  # call to ensure pendings preps are up-to-date

            # Check if preps are finished
            if c.preps_finished:
                return render(request, "brewery/brewing.html", context)
            else:
                logging.warn("brewing: preparations need to be checked.")
                return HttpResponseRedirect(reverse("brewing", kwargs={"cid": c.id}))

        # Brewing: processing
        if request.POST.get("brew_next"):
            logging.debug("brewing: brew_next")
            f_brewprotocol = BrewingProtocol(request.POST)

            """ DO WE NEED THIS HERE? """
            step = c.current_step
            # hopping = None

            # Check if current step contains hop, then load it's calculation
            # if step.category.name == "Würzekochung":
            # hopping = HopCalculation.objects.filter(charge=c).filter(step=step)
            # if hopping:
            #    step = load_calculated_hopping(step, hopping)
            # logging.debug("brewing: hopping for %s is %s", step, hopping.count())

            t_start = datetime.strptime(
                request.POST.get("t_start")[:-1], "%Y%m%d%H%M%S%f"
            )
            """ END: DO WE NEED THIS HERE? """

            if f_brewprotocol.is_valid():
                # Save current step to protocol
                logging.debug("brewing: save current step %s to protocol", step)
                c.processing(f_brewprotocol.cleaned_data["comment"], t_start)
            else:
                logging.warn("brewing: protocol validation failed!")

            # return render(request, "brewery/brewing.html", context)
            return HttpResponseRedirect(reverse("brewing", kwargs={"cid": c.id}))

        # Preparations: start preparations
        else:
            if request.POST.get("recalculate"):
                c.calculate_hops(True)

            # Get preparations for charge
            preparations_tbd = zip(
                c.preparations(),
                [
                    PendingPreparationForm(prefix=str(item), instance=item)
                    for item in c.preparations()
                ],
            )

            # Collecting missing ingredients
            total_ibu, hops = c.get_calculated_hops()
            context["pending_preps"] = preparations_tbd
            context["ingredients"] = c.calculate_ingredients()
            context["total_ibu"] = total_ibu
            context["calc_hop_ingr"] = hops
            context["missing"] = c.get_missing_ingredients()
            return render(request, "brewery/brewing.html", context)


@login_required
def brewing_add(request):
    if request.method == "POST":
        f_charge = BrewingCharge(request.POST)
        if request.POST.get("create"):
            if f_charge.is_valid():
                # Create charge
                c = Charge()
                recipe = f_charge.cleaned_data["recipe"]
                amount = f_charge.cleaned_data["amount"]
                brewmaster = f_charge.cleaned_data["brewmaster"]
                double = False
                c.init(recipe, amount, brewmaster, double)

                return HttpResponseRedirect(reverse("brewing", kwargs={"cid": c.id}))

    else:
        f_charge = BrewingCharge()
    context = {
        "form": f_charge,
        "navi": "brewing",
        "image_url": load_dynamic_bg_image(),
    }
    return render(request, "brewery/brewing.html", context)


@login_required
def protocol(request, cid):
    c = Charge.objects.get(pk=cid)
    context = {}
    if c.brew_protocol:
        context = c.brew_protocol.context(c)
    if c.fermentation_protocol:
        context |= c.fermentation_protocol.context(c)
    return render(request, "brewery/protocol.html", context)


def public_protocol(request, riddle_id):
    try:
        unriddle_id = b64d(riddle_id.encode()).decode().replace("braurat", "")
        context = get_protocol_context(request, int(unriddle_id))
        context["public"] = True
        return render(request, "brewery/protocol.html", context)
    except TypeError:
        return render(request, "brewery/protocol.html", {})


"""
@login_required
def create_pdf_protocol(request, cid):
    return FileResponse(
        processing_pdf(cid),
        as_attachment=True,
        filename=str(Charge.objects.get(pk=cid)) + "_protokoll.pdf",
    )
"""


@login_required
def fermentation(request, cid):
    logging.debug("fermentation: starting")
    c = Charge.objects.get(pk=cid)

    protocol = c.fermentation_protocol

    context = protocol.context(c)
    context["form"] = FermentationProtocolForm()
    context["cform"] = FinishFermentationForm()
    context["f_keg_select"] = KegSelectForm()
    context["f_charge_wort"] = InitFermentationForm()

    if request.POST:
        if request.POST.get("continue"):
            logging.debug("fermentation: save reached wort")
            f_init_fermentation = InitFermentationForm(request.POST)
            if f_init_fermentation.is_valid():
                c.reached_wort = f_init_fermentation.cleaned_data["reached_wort"]
                # checking if ispindel is activated
                if f_init_fermentation.cleaned_data["use_ispindel"] == "True":
                    c.ispindel = True
                    c.save()
                    context["plot"] = get_plot(c)
                    logging.debug("fermentation: ispindel activated")
                else:
                    c.fermentation = True

                c.save()
                return render(request, "brewery/brewing.html", context)

        # checking if fermentation is finished
        if request.POST.get("save"):
            c_form = FinishFermentationForm(request.POST, instance=c)
            f_keg_select = KegSelectForm(request.POST)
            if c_form.is_valid():
                c_form.save(commit=False)
                c.finished = True
                c.save()
                c_form.save()
                if c.ispindel:
                    logging.debug("fermentation: saving fermentation data")
                    save_plot(c)
                if f_keg_select.is_valid():
                    for keg in f_keg_select.cleaned_data["id"]:
                        keg.content = c
                        keg.filling = timezone.now()
                        keg.save()

                logging.debug(
                    "fermentation: fermentation is finished. beer is ready for storing."
                )
                return HttpResponseRedirect(reverse("protocol", kwargs={"cid": c.id}))
            context["cform"] = FinishFermentationForm(instance=c)
            return render(request, "brewery/brewing.html", context)

        # add new manual measure point
        if request.POST.get("add_mp"):
            measure_point = FermentationProtocolForm(request.POST)
            if measure_point.is_valid():
                c.fermentation_protocol.add_mp(measure_point)

            return HttpResponseRedirect(reverse("fermentation", kwargs={"cid": c.id}))

    else:
        # Check if ispindel should be used
        logging.debug("fermentation: using ispindel: %s", c.ispindel)
        if c.ispindel:
            context["plot"] = get_plot(c)

        return render(request, "brewery/brewing.html", context)


@login_required
def recipe(request):
    r = Recipe.objects.all()
    context = {"recipes": r, "navi": "recipe", "image_url": load_dynamic_bg_image()}
    return render(request, "brewery/recipe.html", context)


@login_required
def recipe_detail(request, recipe_id):
    r = Recipe.objects.get(pk=recipe_id)

    if request.method == "POST":
        if request.POST.get("delete"):
            r.delete()
            return HttpResponseRedirect(reverse("recipe"))
        if request.POST.get("add"):
            return HttpResponseRedirect(reverse("step_add", kwargs={"recipe_id": r.id}))

    return render(request, "brewery/recipe_detail.html", r.context())


@login_required
def recipe_add(request):
    logging.debug("recipe_add")
    context = {}
    if request.method == "POST":
        add_recipe = AddRecipe(request.POST)
        select_preparation = SelectPreparation(request.POST)
        if add_recipe.is_valid():
            ar = add_recipe.save(commit=False)
            ar.author = request.user
            ar.creation = datetime.now()
            ar.save()
            if select_preparation.is_valid():
                for item in select_preparation.cleaned_data["preparation"]:
                    ar.add_preparation(item)
            return HttpResponseRedirect(
                reverse("recipe_detail", kwargs={"recipe_id": ar.id})
            )

    add_recipe = AddRecipe()
    select_preparation = SelectPreparation()
    context["add_recipe"] = add_recipe
    context["select_preparation"] = select_preparation
    context["navi"] = "recipe"
    context["image_url"] = load_dynamic_bg_image()

    return render(request, "brewery/recipe_add.html", context)


@login_required
def recipe_edit(request, recipe_id):
    context = {}
    r = Recipe.objects.get(pk=recipe_id)
    preps = SelectPreparation()

    if request.method == "POST":
        if request.POST.get("add"):
            return HttpResponseRedirect(reverse("step_add", kwargs={"recipe_id": r.id}))
        if request.POST.get("delete"):
            r.delete()
            return HttpResponseRedirect(reverse("recipe"))

    form = EditRecipe()
    context["form"] = form
    context["recipe"] = r
    context["steps"] = r.steps()
    # context["unused"] = unused_steps
    context["preps"] = preps
    context["navi"] = "recipe"
    context["image_url"] = load_dynamic_bg_image()

    return render(request, "brewery/recipe_edit.html", context)


@login_required
def step_edit(request, recipe_id: int, step_id: int = None):
    r = Recipe.objects.get(pk=recipe_id)
    # Add a new step
    if step_id is None:
        f_step = StepForm()
        f_successor = StepPredecessorForm(recipe=r.name)
    else:
        step = r.step_by_id(step_id)
        f_step = StepForm(instance=step)
        f_successor = StepPredecessorForm(
            initial={"preds": step.get_predecessor()}, recipe=r.name, step_id=step_id
        )

    if request.method == "POST":
        if step_id is None:
            f_step = StepForm(request.POST)
        else:
            step = r.step_by_id(step_id)
            f_step = StepForm(request.POST, instance=r.step_by_id(step_id))

        if f_step.is_valid():
            step = f_step.save()
            f_pred = StepPredecessorForm(request.POST)

            if f_pred.is_valid():
                pred = f_pred.cleaned_data["preds"]
                if pred is None:  # insert step as head
                    r.add_to_front(step)
                elif pred == r.tail:  # insert step as tail
                    r.add_to_end(step)
                else:  # insert somewhere in between
                    r.add_in_between(pred, step)

                r.update_step_number()

            return HttpResponseRedirect(
                reverse("recipe_detail", kwargs={"recipe_id": r.id})
            )
        else:
            logging.debug(dict(f_step.errors))
            context = {
                "form": f_step,
                "recipe": r,
                "navi": "recipe",
                "image_url": load_dynamic_bg_image(),
            }
            return render(request, "brewery/step_edit.html", context)

    context = {
        "f_successor": f_successor,
        "f_step": f_step,
        "recipe": r,
        "navi": "recipe",
        "image_url": load_dynamic_bg_image(),
    }
    return render(request, "brewery/step_edit.html", context)


@login_required
def storage(request):
    items = Storage.objects.all()
    context = {
        "storage": items,
        "navi": "storage",
        "image_url": load_dynamic_bg_image(),
    }
    return render(request, "brewery/storage.html", context)


@login_required
def storage_add(request):
    logging.debug("storage_add")
    if request.method == "POST":
        form = StorageAddItem(request.POST)
        logging.debug("storage_add: POST")
        if form.is_valid():
            logging.debug("storage_add: form is valid")
            form.save()

            return HttpResponseRedirect(reverse("storage"))

    form = StorageAddItem()
    context = {
        "storage": storage,
        "form": form,
        "navi": "storage",
        "called": "add",
        "image_url": load_dynamic_bg_image(),
    }
    return render(request, "brewery/storage_edit.html", context)


@login_required
def storage_edit(request, s_id):
    item = Storage.objects.get(pk=s_id)
    form = StorageAddItem(instance=item)
    form.fields["alpha"].disabled = True
    if request.method == "POST":
        form = StorageAddItem(request.POST, instance=item)
        if form.is_valid():
            if request.POST.get("save"):
                form.save()
                return HttpResponseRedirect(reverse("storage"))
            if request.POST.get("delete"):
                item.delete()
                return HttpResponseRedirect(reverse("storage"))
    context = {
        "storage": storage,
        "form": form,
        "navi": "storage",
        "called": "edit",
        "image_url": load_dynamic_bg_image(),
    }
    return render(request, "brewery/storage_edit.html", context)


@login_required
def keg(request):
    kegs = Keg.objects.all()
    if request.method == "POST":
        if request.POST.get("edit"):
            keg_forms = [EditKegContent(prefix=str(k), instance=k) for k in kegs]
            zipped_list = zip(kegs, keg_forms)
            context = {"list": zipped_list, "navi": "kegs"}
            return render(request, "brewery/keg.html", context)
        if request.POST.get("save"):
            keg_forms = [
                EditKegContent(request.POST, prefix=str(k), instance=k) for k in kegs
            ]
            for kf in keg_forms:
                if kf.is_valid():
                    kf.save()

            return HttpResponseRedirect(reverse("keg"))
    else:
        context = {"kegs": kegs, "navi": "kegs", "image_url": load_dynamic_bg_image()}
        return render(request, "brewery/keg.html", context)


@login_required
def keg_edit(request, keg_id):
    keg = Keg.objects.get(pk=keg_id)
    form = EditKegContent(prefix=str(keg), instance=keg)
    if request.method == "POST":
        form = EditKegContent(request.POST, prefix=str(keg), instance=keg)
        if form.is_valid():
            if request.POST.get("save"):
                form.save()
                return HttpResponseRedirect(reverse("keg"))
            if request.POST.get("reset"):
                output = BeerOutput()
                output.charge = keg.content
                output.amount = keg.volume
                output.date = datetime.now()
                output.save()

                keg.content = None
                keg.filling = None
                keg.notes = None
                keg.status = "F"
                keg.save()
                return HttpResponseRedirect(reverse("keg"))
    context = {"form": form, "navi": "kegs", "image_url": load_dynamic_bg_image()}
    return render(request, "brewery/keg_edit.html", context)
