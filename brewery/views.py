from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.urls import reverse
from datetime import datetime
import logging, sys
from django.db import transaction
#from influxdb import InfluxDBClient
#import plotly.graph_objects as go
#from plotly.offline import plot
#from plotly.subplots import make_subplots

import base64
from math import pow
from os import environ

from .models import Recipe, Step, Charge, RecipeProtocol, Keg, Hint, FermentationProtocol
from .forms import *

# Used for recipe scaling
AMOUNT_FACTOR = 100

# Configure log level
logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)

def index(request):
    return render(request, 'brewery/index.html')


def protocol_step(charge, step, start_time):
    c = charge
    s = step
    t_start = start_time
    p_step = RecipeProtocol()
    p_step.charge = Charge.objects.get(id=c.id)
    p_step.step = s.id
    p_step.title = s.title
    p_step.description = s.description
    p_step.duration = s.duration
    p_step.ingredient = s.ingredient
    p_step.amount = (s.amount * c.amount) / AMOUNT_FACTOR if s.amount else s.amount
    p_step.tstart = t_start
    p_step.tend = datetime.now()
    return p_step


def storage_delta(charge, step):
    required = charge.amount * step.amount / AMOUNT_FACTOR
    available = Storage.objects.get(name=step.ingredient).amount
    delta = available - required
    return delta


@login_required
def brewing_overview(request):
    c = Charge.objects.filter(finished=True)
    active = Charge.objects.filter(finished=False)
    context = {
        'charge': c,
        'active': active
    }
    return render(request, 'brewery/brewing_overview.html', context)


@login_required
def brewing(request, cid):
    c = get_object_or_404(Charge, pk=cid)
    preps = PreparationProtocol.objects.filter(charge=c)
    context = {}
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
        context['charge'] = c
        context['t_start'] = datetime.now()
        context['step'] = step
        context['hint'] = Hint.objects.filter(step__id=step.id)
        context['protocol'] = RecipeProtocol.objects.filter(charge=cid)
        context['form'] = BrewingProtocol()

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
            finished = not(preps.filter(check=False).exists())
            context = {'charge': c, 'list': zip(preps, preps_form)}

            # Check if preps are finished
            if finished:
                logging.debug("brewing: preparations finished")
                c.preps_finished = True
                c.save()
                step = Step.objects.get(pk=c.recipe.first)
                step.amount = (step.amount * c.amount) / AMOUNT_FACTOR if step.amount else step.amount
                context['step'] = step
                context['t_start'] = datetime.now()
                context['hint'] = Hint.objects.filter(step__id=step.id)
                context['form'] = BrewingProtocol()
                return render(request, 'brewery/brewing.html', context)
            else:
                logging.debug("brewing: there are still preparations todo.")
                return render(request, 'brewery/brewing.html', context)

        # Brewing: get next step
        if request.POST.get('brew_next'):
            logging.debug("brewing: get next step")
            cid = request.POST.get('charge')
            c = Charge.objects.get(pk=cid)
            p_form = BrewingProtocol(request.POST)
            step = c.current_step
            logging.debug("brewing: step: %s", step)
            t_start = datetime.strptime(request.POST.get('t_start')[:-1], "%Y%m%d%H%M%S%f")
            if p_form.is_valid():
                # Create step of protocol
                logging.debug("brewing: saving finished step to protocol")
                p_step = protocol_step(c, step, t_start)
                p_step.comment = p_form.cleaned_data['comment']
                p_step.save()
                # Update storage
                if step.amount:
                    logging.debug("brewing: calculate remaining amount of storage item.")
                    item = Storage.objects.get(name=step.ingredient)
                    item.amount = storage_delta(c, step)
                    item.save()
                # Check if there is a next step
                try:
                    step = step.next
                    logging.debug("brewing: get next step: %s", step.next)
                    step.amount = (step.amount * c.amount) / AMOUNT_FACTOR if step.amount else step.amount
                    context['charge'] = c
                    context['t_start'] = datetime.now()
                    context['step'] = step
                    context['hint'] = Hint.objects.filter(step__id=step.id)
                    context['protocol'] = RecipeProtocol.objects.filter(charge=cid)
                    context['form'] = BrewingProtocol()
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
            # form validation error
            else:
                logging.debug("brewing: something went wrong! seems that p_form is not valid.")

        # Preparations: start preparations
        else:
            # Collecting all necessary ingredients
            logging.debug("brewing: calculate necessary ingredients")
            step = Step.objects.get(pk=c.recipe.first)
            ingredients = {}
            while step:
                data = list()
                if step.ingredient:
                    required = c.amount * step.amount / AMOUNT_FACTOR
                    data.append(step.ingredient.name)
                    data.append(required)
                    data.append(step.ingredient.unit.name)
                    if step.ingredient.type in ingredients:
                        tmp = ingredients[step.ingredient.type]
                        tmp.append(data)
                        ingredients[step.ingredient.type] = tmp
                    else:
                        tmp = list()
                        tmp.append(data)
                        ingredients[step.ingredient.type] = tmp
                    logging.debug("ID: %s Ingredient: %s Type: %s Amount: %s", step.id, step.ingredient.name, step.ingredient.type, required)
                if hasattr(step, 'next'):
                    step = step.next
                else:
                    break
            ingredients['Wasser'] = [['Hauptguss', c.recipe.hg * c.amount / AMOUNT_FACTOR, 'Liter'], ['Nachguss', c.recipe.ng * c.amount  / AMOUNT_FACTOR, 'Liter']]
            logging.debug("brewing: ingredients: %s", ingredients.values())
            # Collecting all necessary preparations (finished and not finished)
            logging.debug("brewing: collecting necessary preparations")
            preps_form = [PreparationProtocolForm(prefix=str(item), instance=item) for item in preps]
            zipped_list = zip(preps, preps_form)
            for s in Step.objects.filter(recipe=c.recipe):
                if s.amount:
                    delta = storage_delta(c, s)
            context = {'charge': c, 'list': zipped_list, 'ingredients': ingredients}
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
                c.cid = current_year_month + "." + str(yearly_production)
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
                    preps_protocol.check = False
                    preps_protocol.save()

                return HttpResponseRedirect(reverse('brewing', kwargs={'cid': c.id}))

    else:
        charge_form = BrewingCharge()
    context = {'form': charge_form}
    return render(request, 'brewery/brewing.html', context)


@login_required
def protocol(request, cid):
    c = Charge.objects.get(pk=cid)
    p = RecipeProtocol.objects.filter(charge=c.id)
    d = c.duration
    context = {'protocol': p, 'charge': c, 'duration': d}

    return render(request, 'brewery/protocol.html', context)


@login_required
def fermentation(request, cid):
    c = Charge.objects.get(pk=cid)
    f = FermentationProtocol.objects.filter(charge=c)
    context = {'charge': c, 'fermentation': f, 'form': FermentationProtocolForm()}
    if request.POST:
        if request.POST.get('spindel') == "True":
            c.ispindel = True
            c.save()
            return render(request, 'brewery/fermentation.html', context)
        if request.POST.get('save'):
            form = FermentationProtocolForm(request.POST)
            if form.is_valid():
                form = form.save(commit=False)
                form.charge = c
                form.save()
            context['form'] = FermentationProtocolForm()
            context['fermentation'] = FermentationProtocol.objects.filter(charge=c)
            if request.POST.get('finished'):
                c.finished = True
                c.save()
                return HttpResponseRedirect(reverse('brewing_overview'))
            return render(request, 'brewery/fermentation.html', context)
        else:
            if not c.fermentation:
                c.fermentation = True
                c.save()
        return render(request, 'brewery/fermentation.html', context)
    else:
        return render(request, 'brewery/fermentation.html', context)


@login_required
def spindel(request):
    """"
    client = InfluxDBClient(host='braurat.de', port=8086, username='admin', password=environ['INFLUXDB_PASS'])
    client.switch_database('ispindel')
    q = client.query('SELECT "tilt","temperature", "battery" FROM "measurements"')
    # ['time', 'RSSI', 'battery', 'gravity', 'interval', 'source', 'temp_units', 'temperature', 'tilt'],
    time = []
    tilt = []
    temperature = []
    battery = []
    points = q.get_points()
    for item in points:
        time.append(item['time'])
        # Ploynom: 0.000166916x^3 + -0.01470147x^2 + 0.679876283x + -10.536229152
        x = item['tilt']
        plato = (0.000166916 * pow(x, 3))
        plato = plato - (0.01470147 * pow(x, 2))
        plato = plato + (0.679876283 * x)
        plato = plato - 10.536229152
        tilt.append(plato)

        temperature.append(item['temperature'])
        battery.append(item['battery'])

    fig = make_subplots(specs=[[{"secondary_y": True}]])
    fig.update_layout(
        title="iSpindel",
        xaxis_title="Zeit",
        yaxis_title="Vergärungsgrad",
        yaxis_range=[-10, 40],
        yaxis2=dict(
            title="Grad Celius",
            overlaying='y',
            side='right',
            range=[2, 30]
        ),
        legend_title="Legende",
        font=dict(
            family="Courier New, monospace",
            size=18,
            color="RebeccaPurple"
        )
    )
    fig.add_trace(go.Scatter(x=time, y=tilt,
                             line_shape='spline',
                             mode='lines',
                             name='Plato'),
                  secondary_y=False)
    fig.add_trace(go.Scatter(x=time, y=temperature,
                             line_shape='spline',
                             mode='lines',
                             name='Temepratur'),
                  secondary_y=True)
    fig.add_trace(go.Scatter(x=time, y=battery,
                             line_shape='spline',
                             mode='lines',
                             name='Batterie'))

    plt_div = plot(fig, output_type='div')
    client.close()

    print(len(time))

    return render(request, 'brewery/spindel.html', {'plot': plt_div})
    """
    plt_div = None
    return render(request, 'brewery/spindel.html', {'plot': plt_div})


@login_required
def recipe(request):
    r = Recipe.objects.all()
    context = {'recipes': r}
    return render(request, 'brewery/recipe.html', context)

### HELPER FUNCTION
def get_steps(rid):
    try:
        step = Step.objects.get(pk=rid.first)
    except AttributeError:
        step = None
    s = []
    while step:
        s.append(step)
        try:
            step = step.next
        except AttributeError:
            step = None
    return s


@login_required
def recipe_detail(request, recipe_id):
    r = Recipe.objects.get(pk=recipe_id)
    s = get_steps(r)    
    p = Preparation.objects.filter(recipe=r)

    if request.method == 'POST':
        if request.POST.get('delete'):
            r.delete()
            return HttpResponseRedirect(reverse('recipe'))

    context = {'recipe': r, 'steps': s, 'preparation': p}

    return render(request, 'brewery/recipe_detail.html', context)


@login_required
def recipe_add(request):
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
            return HttpResponseRedirect(reverse('recipe_edit', kwargs={'recipe_id': ar.id}))

    add_recipe = AddRecipe()
    select_preparation = SelectPreparation()
    context = {'add_recipe': add_recipe, 'select_preparation': select_preparation}

    return render(request, 'brewery/recipe_add.html', context)


@login_required
def recipe_edit(request, recipe_id):
    r = Recipe.objects.get(pk=recipe_id)
    s = get_steps(r)
    preps = SelectPreparation()

    # Get steps which aren't properly linked
    unused_steps = Step.objects.filter(recipe=r)
    try:
        used_steps = Step.objects.get(pk=r.first)
    except AttributeError:
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
    context = {'form': form, 'steps': s, 'recipe': r, 'unused': unused_steps, 'preps': preps}

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
                        predecessor = Step.objects.get(pk=s_prev_id)
                        step.prev = None
                        step.save()
                        successor.prev = predecessor
                        successor.save()
                        logging.debug("predecessor: %s -> %s\t successor: %s <- %s", predecessor.id, predecessor.next.id, successor.id, successor.prev.id)
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

            return HttpResponseRedirect(reverse('recipe_edit', kwargs={'recipe_id': r.id}))
        else:
            logging.debug(dict(form.errors))
            context = {'form': form, 'recipe': r}
            return render(request, 'brewery/step_edit.html', context)

    context = {'form': form, 'recipe': r}
    return render(request, 'brewery/step_edit.html', context)


@login_required
def storage(request):
    items = Storage.objects.all()
    context = {'storage': items}
    return render(request, 'brewery/storage.html', context)


@login_required
def storage_add(request):
    form = StorageAddItem(request.POST)
    if request.method == 'POST':
        if form.is_valid():
            form.save()
            return HttpResponseRedirect(reverse('storage'))

    context = {'storage': storage, 'form': form}
    return render(request, 'brewery/storage_add.html', context)


@login_required
def storage_edit(request, s_id):
    item = Storage.objects.get(pk=s_id)
    form = StorageAddItem(instance=item)
    if request.method == 'POST':
        form = StorageAddItem(request.POST, instance=item)
        if form.is_valid():
            if request.POST.get('save'):
                form.save()
                return HttpResponseRedirect(reverse('storage'))
            if request.POST.get('delete'):
                item.delete()
                return HttpResponseRedirect(reverse('storage'))
    context = {'form': form}
    return render(request, 'brewery/storage_edit.html', context)


@login_required
def keg(request):
    kegs = Keg.objects.all()
    if request.method == 'POST':
        print("request.POST: %s" % request.POST)
        if request.POST.get('edit'):
            keg_forms = [EditKegContent(prefix=str(k), instance=k) for k in kegs]
            zipped_list = zip(kegs, keg_forms)
            context = {'list': zipped_list}
            return render(request, 'brewery/keg.html', context)
        if request.POST.get('save'):
            keg_forms = [EditKegContent(request.POST, prefix=str(k), instance=k) for k in kegs]
            for kf in keg_forms:
                if kf.is_valid():
                    kf.save()

            return HttpResponseRedirect(reverse('keg'))
    else:
        context = {'kegs': kegs}
        return render(request, 'brewery/keg.html', context)