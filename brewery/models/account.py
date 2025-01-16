from django.db import models
from datetime import datetime
import pandas as pd
import logging


class Account(models.Model):
    id = models.AutoField(primary_key=True)
    amount = models.FloatField()
    income = models.BooleanField(default=False)
    date = models.DateTimeField()
    description = models.CharField(max_length=200)

    def __str__(self):
        return str(self.id) + "_" + str(self.date)

    def get_balance(self):
        ab = []
        min_month = "2022-01"
        max_month = "2022-12"
        months = pd.date_range(min_month, max_month, freq="MS").strftime("%b").tolist()
        ab.append(months)

        total_amount = []
        cur_year = datetime.now().year
        for i in range(12):
            amount = 0
            monthly_volume = (
                Account.objects.all()
                .filter(date__year=cur_year)
                .filter(date__month=i + 1)
            )
            for mv in monthly_volume:
                if mv.income:
                    amount = amount + mv.amount
                else:
                    amount = amount - mv.amount
            total_amount.append(amount)
        ab.append(total_amount)
        logging.debug(ab)
        return ab
