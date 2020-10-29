from django.shortcuts import render, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect
from django.urls import reverse
from datetime import datetime
#from influxdb import InfluxDBClient
#import plotly.graph_objects as go
#from plotly.offline import plot
#from plotly.subplots import make_subplots

import base64
from math import pow
from os import environ

from .models import Recipe, Step, Charge, RecipeProtocol, Keg, Hint, FermentationProtocol
from .forms import *


def index(request):
    return render(request, 'brewery/index.html')



def protocol_step(charge, step, starttime):
    c = charge
    s = step
    tstart = starttime
    pstep = RecipeProtocol()
    pstep.charge = Charge.objects.get(id=c.id)
    pstep.step = Step.objects.filter(recipe=c.recipe).get(step=s).step
    pstep.title = Step.objects.filter(recipe=c.recipe).get(step=s).title
    pstep.description = Step.objects.filter(recipe=c.recipe).get(step=s).description
    pstep.duration = Step.objects.filter(recipe=c.recipe).get(step=s).duration
    pstep.ingredient = Step.objects.filter(recipe=c.recipe).get(step=s).ingredient
    pstep.amount = Step.objects.filter(recipe=c.recipe).get(step=s).amount
    pstep.amount = Step.objects.filter(recipe=c.recipe).get(step=s).amount
    pstep.tstart = tstart
    pstep.tend = datetime.now()
    return pstep


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
    # Charge complete
    if c.finished:
        return HttpResponseRedirect(reverse('protocol', kwargs={'cid': c.id}))
    # Fermentation: Starting point
    elif c.preps_finished and c.brewing_finished:
        return HttpResponseRedirect(reverse('fermentation', kwargs={'cid': c.id}))
    # Brewing: Restore session
    elif c.preps_finished and not request.POST:
        last_step = RecipeProtocol.objects.filter(charge=cid).last()
        if last_step:
            last_step = last_step.step
        else:
            last_step = 0
        step = Step.objects.filter(recipe=c.recipe).get(step=last_step + 1)
        context['charge'] = c
        context['tstart'] = datetime.now()
        context['step'] = step
        context['hint'] = Hint.objects.filter(step__id=step.id)
        context['next'] = Step.objects.filter(recipe=c.recipe).filter(step=(last_step + 2)).exists()
        context['protocol'] = RecipeProtocol.objects.filter(charge=cid)
        context['form'] = BrewingProtocol()

        return render(request, 'brewery/brewing.html', context)
    # Brewing: Start process if not already finished
    else:
        # Preparations: save current result
        if request.POST.get('preps_save'):
            preps_form = [PreparationProtocolForm(request.POST, prefix=str(item), instance=item) for item in preps]
            for pf in preps_form:
                if pf.is_valid():
                    pf.save()
            return HttpResponseRedirect(reverse('brewing_overview'))

        # Preparations: if finished, continue brewing
        if request.POST.get('preps_next'):
            preps_form = [PreparationProtocolForm(request.POST, prefix=str(item), instance=item) for item in preps]
            for pf in preps_form:
                if pf.is_valid():
                    pf.save()
            # Check for finished preps
            finished = not(preps.filter(check=False).exists())
            context = {'charge': c, 'list': zip(preps, preps_form)}
            if finished:
                c.preps_finished = True
                c.save()
                first_step = Step.objects.filter(recipe=c.recipe).get(step=1)
                context['step'] = first_step
                context['tstart'] = datetime.now()
                context['next'] = Step.objects.filter(recipe=c.recipe).filter(step=(first_step.step+1)).exists()
                context['hint'] = Hint.objects.filter(step__id=first_step.id)
                context['form'] = BrewingProtocol()
                return render(request, 'brewery/brewing.html', context)
            else:
                return render(request, 'brewery/brewing.html', context)

        # Brewing: get next step
        if request.POST.get('brew_next'):
            cid = request.POST.get('charge')
            c = Charge.objects.get(pk=cid)
            pform = BrewingProtocol(request.POST)
            step = int(request.POST.get('step'))
            tstart = datetime.strptime(request.POST.get('tstart')[:-1], "%Y%m%d%H%M%S%f")
            if pform.is_valid():
                # Create step of protocol
                pstep = protocol_step(c, step, tstart)
                pstep.comment = pform.cleaned_data['comment']
                pstep.save()
                next_step_exists = Step.objects.filter(recipe=c.recipe).filter(step=step + 1)
                if next_step_exists:
                    step = Step.objects.filter(recipe=c.recipe).get(step=step + 1)
                    context['charge'] = c
                    context['tstart'] = datetime.now()
                    context['step'] = step
                    context['next'] = Step.objects.filter(recipe=c.recipe).filter(step=step.step + 2)
                    context['hint'] = Hint.objects.filter(step__id=step.id)
                    context['protocol'] = RecipeProtocol.objects.filter(charge=cid)
                    context['form'] = BrewingProtocol()
                    return render(request, 'brewery/brewing.html', context)
                else:
                    # Calculate overall duration time
                    c.duration = datetime.now() - c.production.replace(tzinfo=None)
                    c.brewing_finished = True
                    c.save()
                    context['charge'] = c
                    context['protocol'] = RecipeProtocol.objects.filter(charge=cid)
                    return HttpResponseRedirect(reverse('fermentation', kwargs={'cid': c.id}))
            else:
                print("pform not valid")
        # Preparations: start preparations
        else:
            preps_form = [PreparationProtocolForm(prefix=str(item), instance=item) for item in preps]
            zipped_list = zip(preps, preps_form)
            context = {'charge': c, 'list': zipped_list}
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
                c.save()

                # Create required preparations
                preps = Preparation.objects.filter(recipe__id=c.recipe.id)
                for p in preps:
                    preps_protocol = PreparationProtocol()
                    preps_protocol.charge = c
                    preps_protocol.preparation = p
                    preps_protocol.check = False
                    preps_protocol.save()

                context = {
                    'charge': c,
                    'form': protocol_form,
                    'next': True,
                }
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
    context = {}
    context['charge'] = c
    context['fermentation'] = f
    context['form'] = FermentationProtocolForm()
    if request.POST:
        if request.POST.get('spindel') == "True":
            c.ispindel = True
            c.save()
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


@login_required
def recipe_detail(request, recipe_id):
    r = Recipe.objects.get(pk=recipe_id)
    s = Step.objects.filter(recipe=recipe_id)
    p = Preparation.objects.filter(recipe=r)
    print(p)
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

    return render(request, 'brewery/recipe_new.html', context)


@login_required
def recipe_edit(request, recipe_id):
    r = Recipe.objects.get(pk=recipe_id)
    s = Step.objects.filter(recipe=recipe_id)
    if request.method == 'POST':
        form = EditRecipe(request.POST)
        if request.POST.get('delete'):
            sid = request.POST.get('id')
            dataset = Step.objects.get(id=sid)
            dataset.delete()
            return HttpResponseRedirect(reverse('recipe_edit', kwargs={'recipe_id': r.id}))

        if request.POST.get('save'):
            if form.is_valid():
                s = form.save(commit=False)
                s.recipe = r
                s.save()
                return HttpResponseRedirect(reverse('recipe_edit', kwargs={'recipe_id': r.id}))

    form = EditRecipe()
    context = {'form': form, 'steps': s}

    return render(request, 'brewery/recipe_edit.html', context)


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