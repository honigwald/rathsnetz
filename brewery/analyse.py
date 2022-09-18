from .models import Recipe, Step, Charge, RecipeProtocol, Keg, Hint, FermentationProtocol, HopCalculation, BeerOutput, Account
from datetime import datetime
import logging
import pandas as pd

def get_account_balance():
    ab = []
    min_month = "2022-01"
    max_month = "2022-12"
    months = pd.date_range(min_month, max_month,freq='MS').strftime("%b").tolist()
    ab.append(months)

    total_amount = []
    cur_month = datetime.now().month
    cur_year = datetime.now().year
    for i in range(12):
        amount = 0
        monthly_volume = Account.objects.all().filter(date__year=cur_year).filter(date__month=i+1)
        for mv in monthly_volume:
            if mv.income: 
                amount = amount + mv.amount
            else:
                amount = amount - mv.amount
        total_amount.append(amount)
    ab.append(total_amount)
    logging.debug(ab)
    return ab

def get_beer_balance():
    bb = []
    min_month = "2020-01"
    max_month = "2020-12"
    months = pd.date_range(min_month, max_month,freq='MS').strftime("%b").tolist()
    bb.append(months)

    total_amount = []
    cur_month = datetime.now().month
    cur_year = datetime.now().year
    for i in range(12):
        income_amount = output_amount = 0
        income = Charge.objects.all().filter(production__year=cur_year).filter(production__month=i+1)
        for c in income:
            income_amount = income_amount + c.amount
        output = BeerOutput.objects.all().filter(date__year=cur_year).filter(date__month=i+1)
        for o in output:
            output_amount = output_amount - o.amount
        total_amount.append(income_amount + output_amount)
    bb.append(total_amount)
    return bb


def get_charge_quantity():
    cq = {}
    recipes = Recipe.objects.all()
    for r in recipes:
        total = 0
        charges = Charge.objects.filter(recipe=r).exclude(finished=False)
        for c in charges:
            total = total + c.amount
        cq[r.name] = total
    return cq


def get_beer_in_stock():
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
