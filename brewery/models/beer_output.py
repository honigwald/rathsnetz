from django.db import models
from .charge import Charge
import pandas as pd
from datetime import datetime


class BeerOutput(models.Model):
    id = models.AutoField(primary_key=True)
    charge = models.ForeignKey(Charge, on_delete=models.DO_NOTHING)
    amount = models.FloatField()
    date = models.DateTimeField()

    def __str__(self):
        return str(self.id) + "_" + str(self.amount)

    def get_balance(self):
        bb = []
        min_month = "2020-01"
        max_month = "2020-12"
        months = pd.date_range(min_month, max_month, freq="MS").strftime("%b").tolist()
        bb.append(months)

        total_amount = []
        cur_year = datetime.now().year
        for i in range(12):
            income_amount = output_amount = 0
            income = (
                Charge.objects.all()
                .filter(production__year=cur_year)
                .filter(production__month=i + 1)
            )
            for c in income:
                income_amount = income_amount + c.amount
            output = (
                BeerOutput.objects.all()
                .filter(date__year=cur_year)
                .filter(date__month=i + 1)
            )
            for o in output:
                output_amount = output_amount - o.amount
            total_amount.append(income_amount + output_amount)
        bb.append(total_amount)
        return bb
