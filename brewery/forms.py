from django import forms
from django.forms import Form, ModelForm, Select
from django.contrib.auth.models import User
from .models import Storage, Recipe, Step, Keg, Preparation, PreparationProtocol, FermentationProtocol
from django.core.validators import EMPTY_VALUES, ValidationError
from django.core import validators


class BrewingCharge(forms.Form):
    recipe = forms.ModelChoiceField(queryset=Recipe.objects.all().order_by('name'))
    amount = forms.FloatField()
    brewmaster = forms.ModelChoiceField(queryset=User.objects.all().order_by('username'))


class BrewingProtocol(forms.Form):
    comment = forms.CharField(widget=forms.Textarea(attrs={"rows":3, "cols":30}), max_length=200, required=False)


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
        fields = ['prev', 'title', 'description', 'duration', 'ingredient', 'amount']

    def clean(self):
        ingredient = self.cleaned_data.get('ingredient', None)
        amount = self.cleaned_data.get('amount', None)
        if ingredient and not amount:
            self.errors['amount'] = self.error_class(['Mengenangabe wird benötigt!'])
        if amount and not ingredient:
            self.errors['ingredient'] = self.error_class(['Zutat muss gewählt werden.'])
        return self.cleaned_data