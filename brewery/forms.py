from django import forms
from django.forms import Form, ModelForm, Select
from django.contrib.auth.models import User
from .models import Storage, Recipe, Step, Keg, Preparation, PreparationProtocol, FermentationProtocol


class BrewingCharge(forms.Form):
    recipe = forms.ModelChoiceField(queryset=Recipe.objects.all().order_by('name'))
    amount = forms.FloatField()
    brewmaster = forms.ModelChoiceField(queryset=User.objects.all().order_by('username'))


class BrewingProtocol(forms.Form):
    comment = forms.CharField(max_length=200)


class StorageAddItem(ModelForm):
    class Meta:
        model = Storage
        fields = ['name', 'amount', 'type', 'unit']


class AddRecipe(ModelForm):
    class Meta:
        model = Recipe
        fields = ['name', 'hg', 'ng']


class EditRecipe(ModelForm):
    class Meta:
        model = Step
        exclude = ('recipe',)


class EditKegContent(ModelForm):
    class Meta:
        model = Keg
        fields = ['content', 'status', 'notes', 'filling']

class SelectPreparation(Form):
    preparation = forms.ModelMultipleChoiceField(queryset=Preparation.objects.all(), required=False)


class PreparationProtocolForm(ModelForm):
    class Meta:
        model = PreparationProtocol
        fields = ['check']


class FermentationProtocolForm(ModelForm):
    class Meta:
        model = FermentationProtocol
        fields = ['temperature', 'plato', 'date']


class StepForm(ModelForm):
    description = forms.CharField(required=False)
    duration = forms.DurationField(required=False)

    class Meta:
        model = Step
        fields = ['step', 'prev', 'title', 'description', 'duration', 'ingredient', 'amount']
