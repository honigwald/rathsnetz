from django import forms
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _

from .models import IngredientStorage


class AddRecipe(forms.Form):
    name = forms.CharField()

    def clean_name(self):
        data = self.cleaned_data['name']

        return data


class EditRecipe(forms.Form):
    stepnr = forms.IntegerField(min_value=1, required=True)
    title = forms.CharField(max_length=200, required=True)
    description = forms.CharField(max_length=200, required=True)
    duration = forms.DurationField(required=False)
    ingredient = forms.ModelChoiceField(queryset=IngredientStorage.objects.all().order_by('name'), required=False)
    amount = forms.FloatField(required=False)

    def clean_duration(self):
        data = self.cleaned_data['duration']
        return data

    def clean_amount(self):
        data = self.cleaned_data['amount']
        return data

