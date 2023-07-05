import locale
locale.setlocale(locale.LC_ALL, 'de_DE.UTF-8')
import logging, sys
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.urls import reverse
from django.utils import timezone
from datetime import datetime
from .models import Recipe, Step, Charge, RecipeProtocol, Keg, Hint, FermentationProtocol, HopCalculation, BeerOutput, Account
from .forms import *
from .analyse import *
from .ingredient import *
from .brewing import *
from .ispindel import *
from .protocol import *

import zlib
from base64 import urlsafe_b64encode as b64e, urlsafe_b64decode as b64d
import base64


### STARTING WITH SOME CONFIGURATIONS
# Used for recipe scaling
AMOUNT_FACTOR = 100
# Configure log level
logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
### END OF CONFIGURATIONS


def index(request):
    return render(request, 'brewery/index.html', {'navi': 'overview'})

@login_required
def analyse(request):
    logging.debug("analyse: running now!")
    config = {'displayModeBar': False}
    ### BIER TOTAL
    cq = get_charge_quantity()
    key = []
    value = []
    data = []
    for k, v in cq.items():
        key.append(k)
        value.append(v)
        data.append(go.Bar(name = k, x = [k], y = [v]))
    logging.debug("analyse: %s", data)

    cq_fig = go.Figure(data = data)
    cq_fig.update_layout(
        title='Total: Biermengen',
        xaxis_tickfont_size=14,
        yaxis=dict(
            title='Menge [Liter]',
            titlefont_size=16,
            tickfont_size=14,
        ),
        legend=dict(
            xanchor="right",
            y=1.0,
            bgcolor='rgba(255, 255, 255, 0)',
            bordercolor='rgba(255, 255, 255, 0)'
        ),
        barmode='group',
        bargap=0.3,
        xaxis={'categoryorder':'total descending'},
    )
    cq_plt = plot(cq_fig, output_type='div', config=config)

    ### BIER IM AUGE
    bis = get_beer_in_stock()
    key.clear()
    value.clear()
    for k, v in bis.items():
        key.append(k)
        value.append(v)

    trace = go.Pie(labels = key, values = value)
    data = [trace]
    bis_fig = go.Figure(data = data)
    bis_fig.update_traces(textinfo='value', hole=0.4)
    bis_fig.update_layout(title='Lager: Bier im Auge')
    bis_plt = plot(bis_fig, output_type='div', config=config)

    ### BIER BALANCE
    bb_data = get_beer_balance()
    bb_fig = go.Figure(go.Waterfall(
        name = "20", orientation = "v",
        #measure = ["relative", "relative", "total", "relative", "relative", "total"],
        x = bb_data[0],
        #textposition = "inside",
        #text = ["+60", "+80", "", "-40", "-20", "Total"],
        totals = {"marker":{"color":"deep sky blue", "line":{"color":"blue", "width":3}}},
        y = bb_data[1],
        connector = {"line":{"color":"rgb(63, 63, 63)"}},
    ))

    bb_fig.update_layout(title = "Bier.Balance: Eingang/Ausgang", waterfallgap = 0.1)
    bb_plt = plot(bb_fig, output_type='div', config=config)

    ### GELD BALANCE
    ab_data = get_account_balance()
    ab_fig = go.Figure(go.Waterfall(
        name = "20", orientation = "v",
        #measure = ["relative", "relative", "total", "relative", "relative", "total"],
        x = ab_data[0],
        #textposition = "inside",
        #text = ["+60", "+80", "", "-40", "-20", "Total"],
        totals = {"marker":{"color":"deep sky blue", "line":{"color":"blue", "width":3}}},
        y = ab_data[1],
        connector = {"line":{"color":"rgb(63, 63, 63)"}},
    ))

    ab_fig.update_layout(title = "Geld.Balance: Eingang/Ausgang", waterfallgap = 0.1)
    ab_plt = plot(ab_fig, output_type='div', config=config)

    return render(request, 'brewery/analyse.html', {'navi': 'analyse', 'cq_plt': cq_plt, 'bis_plt': bis_plt, 'bb_plt': bb_plt, 'ab_plt': ab_plt})


@login_required
def brewing_overview(request):
    c = Charge.objects.filter(finished=True)
    active = Charge.objects.filter(finished=False)
    context = {
        'charge': c,
        'active': active,
        'navi': "brewing"
    }
    return render(request, 'brewery/brewing_overview.html', context)


@login_required
def brewing(request, cid):
    context = {}
    c = get_object_or_404(Charge, pk=cid)
    preps = PreparationProtocol.objects.filter(charge=c)
    context['navi'] = "brewing"
    # Charge finished. Goto protocol
    if c.finished:
        logging.debug("brewing: Charge finished [Finished: Preparations, Brewing, Fermentation]")
        return HttpResponseRedirect(reverse('protocol', kwargs={'cid': c.id}))

    # Preparation and Brewing finished. Goto fermentation
    elif c.preps_finished and c.brewing_finished:
        logging.debug("brewing: Continue with fermentation [Finished: Preparations, Brewing]")
        return HttpResponseRedirect(reverse('fermentation', kwargs={'cid': c.id}))

    # Restore session
    elif c.preps_finished and not request.POST:
        logging.debug("brewing: Restoring session [Finished: Preparations]")
        step = c.current_step
        step.amount = (step.amount * c.amount) / AMOUNT_FACTOR if step.amount else step.amount
        hopping = HopCalculation.objects.filter(charge=c).filter(step=step)
        if step.category.name == "Würzekochung" and hopping:
            step = load_calculated_hopping(step, hopping)
        logging.debug("brewing: hopping: Left hops for %s is %s", step, hopping.count())
        next_step = get_next_step(c, step)

        context['charge'] = c
        context['t_start'] = datetime.now()
        context['step'] = step
        context['s_next'] = next_step
        context['hint'] = Hint.objects.filter(step__id=step.id)
        context['recipe'] = get_steps(c.recipe, c, c.amount)
        context['hg'] = c.amount * c.recipe.hg / AMOUNT_FACTOR
        context['ng'] = c.amount * c.recipe.ng / AMOUNT_FACTOR
        context['protocol'] = RecipeProtocol.objects.filter(charge=cid)
        context['form'] = BrewingProtocol()
        context['progress'] = get_progress(c.recipe, step)
        context['navi'] = 'brewing'

        return render(request, 'brewery/brewing.html', context)

    # Start or continue with process
    else:
        logging.debug("brewing: Starting process.")

        # Preparations: save session
        if request.POST.get('preps_save'):
            logging.debug("brewing: Saving preparation status to DB")
            preps_form = [PreparationProtocolForm(request.POST, prefix=str(item), instance=item) for item in preps]
            for pf in preps_form:
                if pf.is_valid():
                    pf.save()
            return HttpResponseRedirect(reverse('brewing_overview'))

        # Preparations: validate preparations and continue
        if request.POST.get('preps_next'):
            logging.debug("brewing: Check if preparations finished")
            preps_form = [PreparationProtocolForm(request.POST, prefix=str(item), instance=item) for item in preps]
            for pf in preps_form:
                if pf.is_valid():
                    pf.save()
            preps_finished = not(preps.filter(done=False).exists())
            context = {'charge': c, 'list': zip(preps, preps_form)}

            # Check if preps are finished
            if preps_finished:
                logging.debug("brewing: preparations finished")
                c.preps_finished = True
                c.save()
                step = Step.objects.get(pk=c.recipe.first)
                step.amount = (step.amount * c.amount) / AMOUNT_FACTOR if step.amount else step.amount
                s_next = step.next
                s_next.amount = (s_next.amount * c.amount) / AMOUNT_FACTOR if s_next.amount else s_next.amount
                context['step'] = step
                context['s_next'] = s_next
                context['t_start'] = datetime.now()
                context['hint'] = Hint.objects.filter(step__id=step.id)
                context['form'] = BrewingProtocol()
                context['recipe'] = get_steps(c.recipe, c, c.amount)
                context['hg'] = c.amount * c.recipe.hg / AMOUNT_FACTOR
                context['ng'] = c.amount * c.recipe.ng / AMOUNT_FACTOR
                context['progress'] = get_progress(c.recipe, step)
                return render(request, 'brewery/brewing.html', context)
            else:
                logging.debug("brewing: there are still preparations todo.")
                context['ingredients'] = calculate_ingredients(c)
                return render(request, 'brewery/brewing.html', context)

        # Brewing: get next step
        if request.POST.get('brew_next'):
            logging.debug("brewing: brew_next")
            cid = request.POST.get('charge')
            c = Charge.objects.get(pk=cid)
            p_form = BrewingProtocol(request.POST)
            step = c.current_step
            hopping = None

            # Check if current step contains hop, then load it's calculation
            if step.category.name == "Würzekochung":
                hopping = HopCalculation.objects.filter(charge=c).filter(step=step)
                if hopping:
                    step = load_calculated_hopping(step, hopping)
                logging.debug("brewing: hopping for %s is %s", step, hopping.count())

            t_start = datetime.strptime(request.POST.get('t_start')[:-1], "%Y%m%d%H%M%S%f")
            if p_form.is_valid():
                # Save current step to protocol
                logging.debug("brewing: save current step %s to protocol", step)
                p_step = protocol_step(c, step, t_start)
                p_step.comment = p_form.cleaned_data['comment']
                p_step.save()
                # Update storage
                if step.amount:
                    logging.debug("brewing: calculate remaining amount of %s in stock.", step.ingredient)
                    item_in_stock = Storage.objects.get(id=step.ingredient.id)
                    item_in_stock.amount = storage_delta(c, step)
                    item_in_stock.save()
                    # delete first element of hop calculations
                    if hopping:
                        hopping = HopCalculation.objects.filter(charge=c).filter(step=step)
                        logging.debug("brewing: delete first elemet (%s) of hop calculation's (%s).", hopping[0].ingredient, hopping)
                        hopping[0].delete()

                # Check if there still is hopping neccassary
                if not hopping:
                    # Check if there is a next step
                    try:
                        step = step.next
                        logging.debug("brewing: get next step: %s", step)
                        step.amount = (step.amount * c.amount) / AMOUNT_FACTOR if step.amount else step.amount

                        # Check if current step contains hop, then load it's calculation
                        if step.category.name == "Würzekochung":
                            hopping = HopCalculation.objects.filter(charge=c).filter(step=step)
                            if hopping:
                                step = load_calculated_hopping(step, hopping)
                            logging.debug("brewing: hopping for %s is %s", step, hopping.count())

                        cur_step_succ = get_next_step(c, step)
                        logging.debug("brewing: get successor of %s. Successor: %s", step, cur_step_succ)

                        context['charge'] = c
                        context['t_start'] = datetime.now()
                        context['step'] = step
                        context['s_next'] = cur_step_succ
                        context['hint'] = Hint.objects.filter(step__id=step.id)
                        context['protocol'] = RecipeProtocol.objects.filter(charge=cid)
                        context['form'] = BrewingProtocol()
                        context['recipe'] = get_steps(c.recipe, c, c.amount)
                        context['hg'] = c.amount * c.recipe.hg / AMOUNT_FACTOR
                        context['ng'] = c.amount * c.recipe.ng / AMOUNT_FACTOR
                        context['progress'] = get_progress(c.recipe, step)
                        c.current_step = step
                        c.save()
                        return render(request, 'brewery/brewing.html', context)
                    # Brewing: Finished
                    except AttributeError:
                        logging.debug("brewing: brewing process finished. continue with fermentation")
                        # Calculate overall duration time
                        c.duration = datetime.now() - c.production.replace(tzinfo=None)
                        c.brewing_finished = True
                        c.save()
                        context['charge'] = c
                        context['protocol'] = RecipeProtocol.objects.filter(charge=cid)
                        return HttpResponseRedirect(reverse('fermentation', kwargs={'cid': c.id}))
                else:
                    logging.debug("brewing: Left hops for this step: %s", hopping.count())

                    step = load_calculated_hopping(step, hopping)
                    cur_step_succ = get_next_step(c, step)
                    logging.debug("brewing: get successor of %s. Successor: %s", step, cur_step_succ)

                    context['charge'] = c
                    context['t_start'] = datetime.now()
                    context['step'] = step
                    context['s_next'] = cur_step_succ
                    context['hint'] = Hint.objects.filter(step__id=step.id)
                    context['protocol'] = RecipeProtocol.objects.filter(charge=cid)
                    context['form'] = BrewingProtocol()
                    context['recipe'] = get_steps(c.recipe, c, c.amount)
                    context['hg'] = c.amount * c.recipe.hg / AMOUNT_FACTOR
                    context['ng'] = c.amount * c.recipe.ng / AMOUNT_FACTOR
                    context['progress'] = get_progress(c.recipe, step)
                    context['navi'] = 'brewing'
                    c.current_step = step
                    c.save()
                    return render(request, 'brewery/brewing.html', context)
            # form validation error
            else:
                logging.debug("brewing: something went wrong! seems that p_form is not valid.")

        # Preparations: start preparations
        else:
            if request.POST.get('recalculate'):
                c.hop_calculation_finished = False
                c.save()
                hops = HopCalculation.objects.filter(charge=c.id)
                for hop in hops:
                    hop.delete()
            # Collecting all necessary ingredients
            logging.debug("brewing: calculate necessary ingredients")
            ingredients = calculate_ingredients(c)
            logging.debug("brewing: ingredients: %s", ingredients.values())
            logging.debug("brewing: recipe: %s", Step.objects.filter(recipe=c.recipe))
            # Collecting all necessary preparations (finished and not finished)
            logging.debug("brewing: collecting necessary preparations")
            preps_form = [PreparationProtocolForm(prefix=str(item), instance=item) for item in preps]
            zipped_list = zip(preps, preps_form)
            # Collecting missing ingredients
            missing_ingredients = list()
            for s in Step.objects.filter(recipe=c.recipe):
                if s.amount:
                    delta = storage_delta(c, s)
                    if not delta:
                        missing_ingredients.append(s.ingredient)
            calculated_hop_ingredients = HopCalculation.objects.filter(charge=c.id)
            total_ibu = 0
            for item in HopCalculation.objects.filter(charge=c):
                total_ibu += item.ibu
            context = {'charge': c, 'list': zipped_list, 'ingredients': ingredients, 'total_ibu': round(total_ibu,1), 'missing': missing_ingredients, 'calc_hop_ingr': calculated_hop_ingredients, 'navi': 'brewing'}
            return render(request, 'brewery/brewing.html', context)

@login_required
def brewing_add(request):
    if request.method == 'POST':
        charge_form = BrewingCharge(request.POST)
        protocol_form = BrewingProtocol(request.POST)
        if request.POST.get('create'):
            if charge_form.is_valid():
                # Create charge
                c = Charge()
                # Calculate charge ID
                current_year = datetime.now().strftime("%Y")
                yearly_production = Charge.objects.filter(production__contains=current_year + "-").count() + 1
                current_year_month = datetime.now().strftime("%Y%m")
                # Create new charge
                c.cid = current_year_month + "." + str(yearly_production).zfill(2)
                c.recipe = charge_form.cleaned_data['recipe']
                c.amount = charge_form.cleaned_data['amount']
                c.brewmaster = charge_form.cleaned_data['brewmaster']
                c.production = datetime.now()
                c.current_step = Step.objects.get(pk=c.recipe.first)
                c.save()

                # Create required preparations
                preps = Preparation.objects.filter(recipe__id=c.recipe.id)
                for p in preps:
                    preps_protocol = PreparationProtocol()
                    preps_protocol.charge = c
                    preps_protocol.preparation = p
                    preps_protocol.done = False
                    preps_protocol.save()

                return HttpResponseRedirect(reverse('brewing', kwargs={'cid': c.id}))

    else:
        charge_form = BrewingCharge()
    context = {'form': charge_form, 'navi': 'brewing'}
    return render(request, 'brewery/brewing.html', context)


def get_protocol_context(request, cid):
    context = {}
    c = Charge.objects.get(pk=cid)
    context['charge'] = c
    context['protocol'] = RecipeProtocol.objects.filter(charge=c.id)
    context['hg'] = c.amount * c.recipe.hg / AMOUNT_FACTOR
    context['ng'] = c.amount * c.recipe.ng / AMOUNT_FACTOR
    try:
        real_restextract = 0.1808 * c.reached_wort + 0.8192 - c.restextract
    except TypeError:
        real_restextract = None
    try:
        context['evg'] = (c.reached_wort - real_restextract) * 100 / c.reached_wort
    except TypeError:
        context['evg'] = None
    try:
        context['alc'] = (c.reached_wort - real_restextract) / (2.0665 - 0.010665 * c.reached_wort)
    except TypeError:
        context['alc'] = None
    context['navi'] = 'brewing'

    if c.ispindel:
        context['plot'] = get_plot(c)
    else:
        context['fermentation'] = FermentationProtocol.objects.filter(charge=c.id)

    host_port = request.META['HTTP_HOST']
    riddle_id = base64.b64encode(("braurat" + str(c.id)).encode())
    context['qrurl'] = "https://" + host_port + "/public/protocol/" + riddle_id.decode()

    return context


@login_required
def protocol(request, cid):
    return render(request, 'brewery/protocol.html', get_protocol_context(request, cid))


def public_protocol(request, riddle_id):
    try:
        unriddle_id = base64.b64decode(riddle_id.encode()).decode().replace("braurat","")
        context = get_protocol_context(request, int(unriddle_id))
        context['public'] = True
        return render(request, 'brewery/protocol.html', context)
    except:
        return render(request, 'brewery/protocol.html', {})


@login_required
def create_pdf_protocol(request, cid):
    return FileResponse(processing_pdf(cid), as_attachment=True, filename=str(Charge.objects.get(pk=cid))+'_protokoll.pdf')


@login_required
def fermentation(request, cid):
    context = {}
    logging.debug("fermentation: starting")
    c = Charge.objects.get(pk=cid)
    f = FermentationProtocol.objects.filter(charge=c)
    context['charge'] = c
    context['fermentation'] = f
    context['form'] = FermentationProtocolForm()
    context['cform'] = FinishFermentationForm()
    context['f_keg_select'] = KegSelectForm()
    context['f_charge_wort'] = InitFermentationForm()
    context['navi'] = 'brewing'

    if request.POST:
        if request.POST.get('continue'):
            logging.debug("fermentation: save reached wort")
            f_init_fermenation = InitFermentationForm(request.POST)
            if f_init_fermenation.is_valid():
                c.reached_wort = f_init_fermenation.cleaned_data['reached_wort']
                c.save()
                # checking if ispindel is activated
                if f_init_fermenation.cleaned_data['use_ispindel'] == "True":
                    c.ispindel = True
                    c.save()
                    context['plot'] = get_plot(c)
                    logging.debug("fermentation: ispindel activated")
                    return render(request, 'brewery/fermentation.html', context)
                else:
                    c.fermentation = True
                    c.save()
                    return render(request, 'brewery/fermentation.html', context)

        # checking if fermentation is finished
        if request.POST.get('save'):
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
                    for keg in f_keg_select.cleaned_data['id']:
                        keg.content = c
                        keg.filling = timezone.now()
                        keg.save()

                logging.debug("fermentation: fermentation is finished. beer is ready for storing.")
                return HttpResponseRedirect(reverse('protocol', kwargs={'cid': c.id}))
            context['cform'] = FinishFermentationForm(instance=c)
            return render(request, 'brewery/fermentation.html', context)

        # checking for new measure point
        if request.POST.get('add_mp'):
            logging.debug("fermentation: adding new measure point")
            form = FermentationProtocolForm(request.POST)
            if form.is_valid():
                logging.debug("fermentation: form.is_valid")
                form = form.save(commit=False)
                form.charge = c
                form.step = FermentationProtocol.objects.filter(charge=c).count() + 1
                form.save()
            context['form'] = FermentationProtocolForm()
            context['fermentation'] = FermentationProtocol.objects.filter(charge=c)
            logging.debug("fermentation: rendering manual fermentation-protocol and -form.")
            return render(request, 'brewery/fermentation.html', context)

    else:
        # Check if ispindel should be used
        logging.debug("fermentation: using ispindel: %s", c.ispindel)
        if c.ispindel:
            context['plot'] = get_plot(c)

        return render(request, 'brewery/fermentation.html', context)



@login_required
def recipe(request):
    r = Recipe.objects.all()
    context = {'recipes': r}
    context['navi'] = 'recipe'
    return render(request, 'brewery/recipe.html', context)

@login_required
def recipe_detail(request, recipe_id):
    context = {}
    r = Recipe.objects.get(pk=recipe_id)
    s = get_steps(r, None, AMOUNT_FACTOR)
    p = Preparation.objects.filter(recipe=r)

    if request.method == 'POST':
        if request.POST.get('delete'):
            r.delete()
            return HttpResponseRedirect(reverse('recipe'))
        if request.POST.get('add'):
            return HttpResponseRedirect(reverse('step_add', kwargs={'recipe_id': r.id}))

    context['recipe'] = r
    context['steps'] = s
    context['preparation'] = p
    context['navi'] = 'recipe'

    return render(request, 'brewery/recipe_detail.html', context)


@login_required
def recipe_add(request):
    context = {}
    if request.method == 'POST':
        add_recipe = AddRecipe(request.POST)
        select_preparation = SelectPreparation(request.POST)
        if add_recipe.is_valid():
            ar = add_recipe.save(commit=False)
            ar.author = request.user
            ar.creation = datetime.now()
            ar.save()
            if select_preparation.is_valid():
                for item in select_preparation.cleaned_data['preparation']:
                    prep = get_object_or_404(Preparation, short=item)
                    prep.recipe.add(ar)
            return HttpResponseRedirect(reverse('recipe_detail', kwargs={'recipe_id': ar.id}))

    add_recipe = AddRecipe()
    select_preparation = SelectPreparation()
    context['add_recipe'] = add_recipe
    context['select_preparation'] = select_preparation
    context['navi'] = 'recipe'

    return render(request, 'brewery/recipe_add.html', context)


@login_required
def recipe_edit(request, recipe_id):
    context = {}
    r = Recipe.objects.get(pk=recipe_id)
    s = get_steps(r, None, AMOUNT_FACTOR)
    preps = SelectPreparation()

    # Get steps which aren't properly linked
    unused_steps = Step.objects.filter(recipe=r)
    try:
        used_steps = Step.objects.get(pk=r.first)
    except Step.DoesNotExist:
        used_steps = None

    while used_steps:
        unused_steps = unused_steps.exclude(pk=used_steps.id)
        try:
            used_steps = used_steps.next
        except AttributeError:
            used_steps = None
    
    if request.method == 'POST':
        if request.POST.get('add'):
            return HttpResponseRedirect(reverse('step_add', kwargs={'recipe_id': r.id}))
        if request.POST.get('delete'):
            r.delete()
            return HttpResponseRedirect(reverse('recipe'))

    form = EditRecipe()
    context['form'] = form
    context['steps'] = s
    context['recipe'] = r
    context['unused'] = unused_steps
    context['preps'] = preps
    context['navi'] = 'recipe'

    return render(request, 'brewery/recipe_edit.html', context)


@login_required
def step_edit(request, recipe_id, step_id=None):
    logging.debug("step_edit(request, recipe_id: %s, step_id: %s)", recipe_id, step_id)
    r = Recipe.objects.get(pk=recipe_id)
    if step_id is None:
        form = StepForm()
        # Filter recipe steps
        form.fields["prev"].queryset = Step.objects.filter(recipe=recipe_id).order_by('step')
        s = None
    else:
        s = Step.objects.filter(recipe=recipe_id).get(pk=step_id)
        form = StepForm(instance=s)
        # Filter recipe steps and exclude current
        form.fields["prev"].queryset = Step.objects.filter(recipe=recipe_id).exclude(pk=step_id).order_by('step')
    if request.method == 'POST':
        if step_id is None:
            form = StepForm(request.POST)
        else:
            form = StepForm(request.POST, instance=s)

        # Get previous step
        try:
            prev = Step.objects.get(pk=form.data['prev'])
        except ValueError:
            prev = False

        # Get successor of previous step
        try:
            prev_next = prev.next
        except AttributeError:
            prev_next = False

        # Get values out of step
        if s:
            try:
                s_has_next = s.next
                s_next_id = s.next.id
            except AttributeError:
                s_has_next = False
            try:
                s_prev = Step.objects.get(pk=s.id).prev
                s_prev_id = s.prev.id
            except AttributeError:
                s_prev = False
                s_prev_id = False
        else:
            s_has_next = False
            s_prev = False
            s_next_id = False

        if form.is_valid():
            step = form.save(commit=False)
            step.recipe = r
            # check if step is already present and is changed
            if prev == s_prev and s:
                logging.debug("linked list is not updated")
                step.save()

            # Update linked list
            else:
                logging.debug("linked list will get updated")

                # Insert as first element of list
                if not prev:
                    logging.debug("step gets inserted as first element")
                    logging.debug("step.next: %s", s_has_next)
                    if s_has_next:
                        successor = Step.objects.get(pk=s_next_id)
                        predecessor = Step.objects.get(pk=s_prev_id)
                        step.prev = None
                        step.save()
                        successor.prev = predecessor
                        successor.save()
                        logging.debug("predecessor: %s -> %s\t successor: %s <- %s", predecessor.id, predecessor.next.id, successor.id, successor.prev.id)
                    step.save()
                    # moving old ll-first to successor of new ll-first
                    if r.first:
                        old_first = Step.objects.get(pk=r.first)
                        old_first.prev = step
                        old_first.save()
                        old_first_id = old_first.id
                        r.first = step.id
                        r.save()
                    else:
                        old_first_id = None
                    r.first = step.id
                    r.save()
                    logging.debug("old_first: %s\t new_first: %s\t first_in_recipe: %s", old_first_id, step.id, r.first)

                # previous element is linked with successor
                elif prev_next and step_id != r.first:
                    logging.debug("step gets inserted between first and last element")
                    logging.debug("step.next: %s", s_has_next)
                    if s_has_next:
                        successor = Step.objects.get(pk=s_next_id)
                        predecessor = Step.objects.get(pk=s_prev_id)
                        step.prev = None
                        step.save()
                        successor.prev = predecessor
                        successor.save()
                        logging.debug("predecessor: %s -> %s\t successor: %s <- %s", predecessor.id, predecessor.next.id, successor.id, successor.prev.id)
                    prev_next.prev = None
                    prev_next.save()
                    step.prev = prev
                    step.save()
                    prev_next.prev = step
                    prev_next.save()
                    logging.debug("pred: %s -> %s\t curr: %s -> %s\t succ: %s", prev.id, prev.next.id, step.id, step.next.id, prev_next.id)

                # customized element is head of the list
                elif prev_next and step_id == r.first:
                    logging.debug("first step gets inserted between first and last element")
                    successor = Step.objects.get(pk=s_next_id)
                    successor.prev = None
                    r.first = successor.id
                    r.save()
                    successor.save()
                    logging.debug("successor moved to first. succ: %s, succ.prev: %s, r.first: %s", successor.id, successor.prev, r.first)
                    prev.next.prev = step
                    prev.next.save()
                    step.prev = prev
                    step.save()
                    logging.debug("pred: %s -> %s\t curr: %s -> %s\t succ: %s", prev.id, prev.next.id, step.id, step.next.id, prev_next.id)

                # previous element is at the end of the list
                elif not prev_next:
                    logging.debug("step gets inserted as last element")
                    logging.debug("step.next: %s", s_has_next)
                    if s_has_next:
                        successor = Step.objects.get(pk=s_next_id)
                        try:
                            predecessor = Step.objects.get(pk=s_prev_id)
                        except Step.DoesNotExist:
                            predecessor = None
                        if predecessor:
                            step.prev = None
                            step.save()
                            successor.prev = predecessor
                            successor.save()
                            logging.debug("predecessor: %s -> %s\t successor: %s <- %s", predecessor.id, predecessor.next.id, successor.id, successor.prev.id)
                        else:
                            successor.prev = None
                            successor.save()
                            r.first = successor.id
                            r.save()
                    step.prev = prev
                    step.save()

                # default case
                else:
                    logging.debug("Something went wrong! This is the default case, so nothing happened...")

            # Update recipe steps
            elem = Step.objects.get(pk=r.first)
            snr = 1
            recipe_steps = Step.objects.all().filter(recipe=r).count()
            logging.debug("Updating step numbers")
            while True or snr == recipe_steps:
                elem.step = snr
                elem.save()
                if not hasattr(elem, 'next'):
                    logging.debug("step: %2.d id: %s -> %s", snr, elem.id, None)
                    break
                logging.debug("step: %2.d id: %s -> %s", snr, elem.id, elem.next.id)
                elem = elem.next
                snr = snr + 1

            return HttpResponseRedirect(reverse('recipe_detail', kwargs={'recipe_id': r.id}))
        else:
            logging.debug(dict(form.errors))
            context = {'form': form, 'recipe': r, 'navi': 'recipe'}
            return render(request, 'brewery/step_edit.html', context)

    context = {'form': form, 'recipe': r, 'navi': 'recipe'}
    return render(request, 'brewery/step_edit.html', context)


@login_required
def storage(request):
    items = Storage.objects.all()
    context = {'storage': items, 'navi': 'storage'}
    return render(request, 'brewery/storage.html', context)


@login_required
def storage_add(request):
    logging.debug("storage_add")
    if request.method == 'POST':
        form = StorageAddItem(request.POST)
        logging.debug("storage_add: POST")
        if form.is_valid():
            logging.debug("storage_add: form is valid")
            form.save()

            return HttpResponseRedirect(reverse('storage'))

    form = StorageAddItem()
    context = {'storage': storage, 'form': form, 'navi': 'storage', 'called': 'add'}
    return render(request, 'brewery/storage_edit.html', context)


@login_required
def storage_edit(request, s_id):
    item = Storage.objects.get(pk=s_id)
    form = StorageAddItem(instance=item)
    form.fields['alpha'].disabled = True
    if request.method == 'POST':
        form = StorageAddItem(request.POST, instance=item)
        if form.is_valid():
            if request.POST.get('save'):
                form.save()
                return HttpResponseRedirect(reverse('storage'))
            if request.POST.get('delete'):
                item.delete()
                return HttpResponseRedirect(reverse('storage'))
    context = {'storage': storage, 'form': form, 'navi': 'storage', 'called': 'edit'}
    return render(request, 'brewery/storage_edit.html', context)


@login_required
def keg(request):
    kegs = Keg.objects.all()
    if request.method == 'POST':
        if request.POST.get('edit'):
            keg_forms = [EditKegContent(prefix=str(k), instance=k) for k in kegs]
            zipped_list = zip(kegs, keg_forms)
            context = {'list': zipped_list, 'navi': 'kegs'}
            return render(request, 'brewery/keg.html', context)
        if request.POST.get('save'):
            keg_forms = [EditKegContent(request.POST, prefix=str(k), instance=k) for k in kegs]
            for kf in keg_forms:
                if kf.is_valid():
                    kf.save()

            return HttpResponseRedirect(reverse('keg'))
    else:
        context = {'kegs': kegs, 'navi': 'kegs'}
        return render(request, 'brewery/keg.html', context)

@login_required
def keg_edit(request, keg_id):
    keg = Keg.objects.get(pk=keg_id)
    form = EditKegContent(prefix=str(keg), instance=keg)
    if request.method == 'POST':
        form = EditKegContent(request.POST, prefix=str(keg), instance=keg)
        if form.is_valid():
            if request.POST.get('save'):
                form.save()
                return HttpResponseRedirect(reverse('keg'))
            if request.POST.get('reset'):
                output = BeerOutput()
                output.charge = keg.content
                output.amount = keg.volume
                output.date = datetime.now()
                output.save()

                keg.content = None
                keg.filling = None
                keg.notes = None
                keg.status = 'F'
                keg.save()
                return HttpResponseRedirect(reverse('keg'))
    context = {'form': form, 'navi': 'kegs'}
    return render(request, 'brewery/keg_edit.html', context)
