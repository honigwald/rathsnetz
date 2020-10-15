from django import forms
from django.forms import ModelForm
from django.core.exceptions import ValidationError
from django.utils.translation import ugettext_lazy as _
from django.contrib.auth.models import User

from .models import IngredientStorage, Recipe

from .models import IngredientStorage, Recipe, Step

class AddRecipe(forms.Form):
    name = forms.CharField()




class BrewingCharge(forms.Form):
    recipe = forms.ModelChoiceField(queryset=Recipe.objects.all().order_by('name'))
    amount = forms.FloatField()
    brewmaster = forms.ModelChoiceField(queryset=User.objects.all().order_by('username'))

class BrewingProtocol(forms.Form):
    comment = forms.CharField(max_length=200)


class StorageAddItem(ModelForm):
    class Meta:
        model = IngredientStorage
        fields = ['name', 'amount', 'type', 'unit']


class AddRecipe(ModelForm):
    class Meta:
        model = Recipe
        fields = ['name']


class EditRecipe(ModelForm):
    def __init__(self, *args, **kwargs):
        super(EditRecipe,self).__init__(*args, **kwargs)
        if 'recipe' in kwargs:
            recipe = kwargs.pop('recipe')
            self.fields['recipe'].initial = recipe

    class Meta:
        model = Step
        exclude = ('recipe',)
