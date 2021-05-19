import logging, sys, json
from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.urls import reverse
from datetime import datetime
from math import pow
from .models import Recipe, Step, Charge, RecipeProtocol, Keg, Hint, FermentationProtocol
from .forms import *

import plotly.graph_objects as go
from plotly.offline import plot
from plotly.subplots import make_subplots
from influxdb import InfluxDBClient


### STARTING WITH SOME CONFIGURATIONS
# Used for recipe scaling
AMOUNT_FACTOR = 100
CONFIG_FILE = './brewery/config.json'

# Configure log level
logging.basicConfig(stream=sys.stderr, level=logging.DEBUG)
### END OF CONFIGURATIONS


def index(request):
    return render(request, 'brewery/index.html', {'navi': 'overview'})


def analyse(request):
    return render(request, 'brewery/analyse.html', {'navi': 'analyse'})


def protocol_step(charge, step, start_time):
    c = charge
    s = step
    t_start = start_time
    p_step = RecipeProtocol()
    p_step.charge = Charge.objects.get(id=c.id)
    p_step.step = s.step
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
        'active': active,
        'navi': "brewing"
    }
    return render(request, 'brewery/brewing_overview.html', context)


def calculate_ingredients(charge):
    step = Step.objects.get(pk=charge.recipe.first)
    ingredients = {}
    while step:
        data = list()
        if step.ingredient:
            required = charge.amount * step.amount / AMOUNT_FACTOR
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
    ingredients['Wasser'] = [['Hauptguss', charge.recipe.hg * charge.amount / AMOUNT_FACTOR, 'Liter'],
                             ['Nachguss', charge.recipe.ng * charge.amount / AMOUNT_FACTOR, 'Liter']]
    return ingredients


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
        try:
            s_next = step.next
            s_next.amount = (s_next.amount * c.amount) / AMOUNT_FACTOR if s_next.amount else s_next.amount
        except Step.DoesNotExist:
            s_next = None
        context['charge'] = c
        context['t_start'] = datetime.now()
        context['step'] = step
        context['s_next'] = s_next
        context['hint'] = Hint.objects.filter(step__id=step.id)
        context['recipe'] = get_steps(c.recipe, c.amount)
        context['hg'] = c.amount * c.recipe.hg / AMOUNT_FACTOR
        context['ng'] = c.amount * c.recipe.ng / AMOUNT_FACTOR
        context['protocol'] = RecipeProtocol.objects.filter(charge=cid)
        context['form'] = BrewingProtocol()
        context['progress'] = get_progress(c.recipe, step)

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
                s_next = step.next
                s_next.amount = (s_next.amount * c.amount) / AMOUNT_FACTOR if s_next.amount else s_next.amount
                context['step'] = step
                context['s_next'] = s_next
                context['t_start'] = datetime.now()
                context['hint'] = Hint.objects.filter(step__id=step.id)
                context['form'] = BrewingProtocol()
                context['recipe'] = get_steps(c.recipe, c.amount)
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
                    logging.debug("brewing: get next step: %s", step)
                    step.amount = (step.amount * c.amount) / AMOUNT_FACTOR if step.amount else step.amount
                    try:
                        s_next = step.next
                        logging.debug("brewing: get new next step: %s", s_next)
                        s_next.amount = (s_next.amount * c.amount) / AMOUNT_FACTOR if s_next.amount else s_next.amount
                    except AttributeError:
                        s_next = None
                    context['charge'] = c
                    context['t_start'] = datetime.now()
                    context['step'] = step
                    context['s_next'] = s_next
                    context['hint'] = Hint.objects.filter(step__id=step.id)
                    context['protocol'] = RecipeProtocol.objects.filter(charge=cid)
                    context['form'] = BrewingProtocol()
                    context['recipe'] = get_steps(c.recipe, c.amount)
                    context['hg'] = c.amount * c.recipe.hg / AMOUNT_FACTOR
                    context['ng'] = c.amount * c.recipe.ng / AMOUNT_FACTOR
                    context['progress'] = get_progress(c.recipe, step)
                    c.current_step = step
                    c.save()
                    logging.debug("brewing: context[recipe]: %s", context['recipe'])
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
            ingredients = calculate_ingredients(c)
            logging.debug("brewing: ingredients: %s", ingredients.values())
            logging.debug("brewing: recipe: %s", Step.objects.filter(recipe=c.recipe))
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
                    preps_protocol.check = False
                    preps_protocol.save()

                return HttpResponseRedirect(reverse('brewing', kwargs={'cid': c.id}))

    else:
        charge_form = BrewingCharge()
    context = {'form': charge_form, 'navi': 'brewing'}
    return render(request, 'brewery/brewing.html', context)


@login_required
def protocol(request, cid):
    context = {}
    c = Charge.objects.get(pk=cid)
    context['charge'] = c
    context['protocol'] = RecipeProtocol.objects.filter(charge=c.id)
    context['hg'] = c.amount * c.recipe.hg / AMOUNT_FACTOR
    context['ng'] = c.amount * c.recipe.ng / AMOUNT_FACTOR
    context['output'] = c.output
    context['evg'] = c.evg
    context['navi'] = 'brewing'

    if c.ispindel:
        context['plot'] = get_plot(c)
    else:
        context['fermentation'] = FermentationProtocol.objects.filter(charge=c.id)

    return render(request, 'brewery/protocol.html', context)


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
    context['navi'] = 'brewing'

    if request.POST:
        # checking if ispindel is activated
        if request.POST.get('spindel') == "True":
            c.ispindel = True
            c.save()
            context['plot'] = get_plot(c)
            logging.debug("fermentation: ispindel activated")
            return render(request, 'brewery/fermentation.html', context)

        # checking if fermentation is finished
        if request.POST.get('finished'):
            c.finished = True
            c.save()
            if c.ispindel:
                logging.debug("fermentation: saving fermentation data")
                save_plot(c)
            logging.debug("fermentation: fermentation is finished. beer is ready for storing.")
            return HttpResponseRedirect(reverse('protocol', kwargs={'cid': c.id}))
        if request.POST.get('save'):
            c_form = FinishFermentationForm(request.POST, instance=c)
            if c_form.is_valid():
                c_form.save(commit=False)
                c.finished = True
                c.save()
                c_form.save()
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

        # default case - this maybe obsolete
        else:
            if not c.fermentation:
                c.fermentation = True
                c.save()
        return render(request, 'brewery/fermentation.html', context)
    else:
        # Check if ispindel should be used
        logging.debug("fermentation: using ispindel: %s", c.ispindel)
        if c.ispindel:
            context['plot'] = get_plot(c)

        return render(request, 'brewery/fermentation.html', context)

def save_plot(charge):
    # Get charge
    logging.debug("save_plot: saving measurements of charge: %s", charge.cid)

    # Getting credentials
    with open(CONFIG_FILE) as json_file:
        data = json.load(json_file)
        for ifdb in data['influxdb']:
            ifdb_host = ifdb['host']
            ifdb_port = ifdb['port']
            ifdb_user = ifdb['user']
            ifdb_pass = ifdb['password']

    logging.debug("save_plot: connecting to influx db")
    client = InfluxDBClient(host=ifdb_host, port=ifdb_port, username=ifdb_user, password=ifdb_pass)
    client.switch_database('ispindel')

    # Build query
    query = 'SELECT * INTO "' + charge.cid + '" FROM "measurements"'
    logging.debug("save_plot: query: %s", query)
    client.query(query)
    logging.debug("save_plot: done.")

    # Cleanup
    query = 'DROP measurement "measurements"'
    client.query(query)
    logging.debug("save_plot: cleaning up.")


def get_plot(charge):
    # Get charge
    logging.debug("get_plot: plot for charge: %s", charge.cid)

    # Getting credentials
    with open(CONFIG_FILE) as json_file:
        data = json.load(json_file)
        for ifdb in data['influxdb']:
            ifdb_host = ifdb['host']
            ifdb_port = ifdb['port']
            ifdb_user = ifdb['user']
            ifdb_pass = ifdb['password']

    logging.debug("get_plot: connecting to influx db")
    client = InfluxDBClient(host=ifdb_host, port=ifdb_port, username=ifdb_user, password=ifdb_pass)
    client.switch_database('ispindel')

    # Build query
    if charge.finished:
        query = 'SELECT "tilt","temperature", "battery" FROM ' + '"' + charge.cid + '"'
        q = client.query(query)
    else:
        q = client.query('SELECT "tilt","temperature", "battery" FROM "measurements"')

    logging.debug("get_plot: querying data from db")
    #logging.debug("get_plot: result: %s", q)
    # ['time', 'RSSI', 'battery', 'gravity', 'interval', 'source', 'temp_units', 'temperature', 'tilt'],
    time = []
    tilt = []
    temperature = []
    battery = []
    points = q.get_points()
    for item in points:
        time.append(item['time'])
        print("Time: {}".format(item['time']))
        # Polynomial: 0.000166916x^3 + -0.01470147x^2 + 0.679876283x + -10.536229152
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
        height=550,
        xaxis_title="Zeit",
        yaxis=dict(
            title_text="Vergärungsgrad [°Plato]",
            tickmode="array",
        ),
        yaxis2=dict(
            title="Temperatur [°C]",
            overlaying='y',
            side='right',
            range=[2, 30]
        ),
        font=dict(
            family="Courier New, monospace",
            size=14,
            color="RebeccaPurple"
        ),
        legend=dict(
            yanchor="top",
            xanchor="right",
            y=0.95,
            x=0.9
        ),
        hovermode='x',
    )
    fig.update_yaxes(automargin=True)
    config = {'responsive': True, 'modeBarButtonsToRemove': ['toggleSpikelines']}
    fig.update_xaxes(showline=True, linewidth=2, linecolor='black')
    fig.update_yaxes(showline=True, linewidth=2, linecolor='black')


    fig.add_trace(go.Scatter(x=time[1:], y=tilt[1:],
                             line_shape='spline',
                             mode='lines',
                             name='Plato'),
                             secondary_y=False)
    fig.add_trace(go.Scatter(x=time[1:], y=temperature[1:],
                             line_shape='spline',
                             mode='lines',
                             name='Temperatur'),
                             secondary_y=True)
    fig.add_trace(go.Scatter(x=time[1:], y=battery[1:],
                             line_shape='spline',
                             mode='lines',
                             name='Batterie',
                             visible='legendonly'))

    plt_div = plot(fig, output_type='div')
    client.close()

    logging.debug("get_plot: process finished")

    return plt_div


@login_required
def recipe(request):
    r = Recipe.objects.all()
    context = {'recipes': r}
    context['navi'] = 'recipe'
    return render(request, 'brewery/recipe.html', context)


### HELPER FUNCTION
def get_steps(rid, amount):
    try:
        step = Step.objects.get(pk=rid.first)
    except Step.DoesNotExist:
        step = None
    s = []
    while step:
        if step.ingredient:
            step.amount = (step.amount * amount) / AMOUNT_FACTOR
            s.append(step)
        else:
            s.append(step)
        try:
            step = step.next
        except AttributeError:
            step = None
    return s


def get_progress(rid, current_step):
    try:
        step = Step.objects.get(pk=rid.first)
    except Step.DoesNotExist:
        step = None

    s = []
    while step:
        s.append(step)
        try:
            step = step.next
        except AttributeError:
            step = None
    print(len(s))
    print(s.index(current_step))

    progress = ((s.index(current_step) + 1) / len(s)) * 100

    return int(progress)




@login_required
def recipe_detail(request, recipe_id):
    context = {}
    r = Recipe.objects.get(pk=recipe_id)
    s = get_steps(r, AMOUNT_FACTOR)
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
    s = get_steps(r, AMOUNT_FACTOR)
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
    context = {'storage': storage, 'form': form, 'navi': 'storage'}
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
    context = {'form': form, 'navi': 'storage'}
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
                keg.content = None
                keg.filling = None
                keg.notes = None
                keg.status = "Unverplant"
                keg.save()
                return HttpResponseRedirect(reverse('keg'))
    context = {'form': form, 'navi': 'kegs'}
    return render(request, 'brewery/keg_edit.html', context)
