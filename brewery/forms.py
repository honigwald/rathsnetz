from django import forms
from django.forms import Form, ModelForm, Select, TextInput, NumberInput
from django.contrib.auth.models import User
from bootstrap_datepicker_plus import DateTimePickerInput, DatePickerInput
from .models import Charge, Storage, Recipe, Step, Keg, Preparation, PreparationProtocol, FermentationProtocol
from django.core.validators import EMPTY_VALUES, ValidationError
from django.core import validators


class BrewingCharge(ModelForm):
    class Meta:
        model = Charge
        fields = ['recipe', 'brewmaster', 'amount']
        widgets = {'recipe': Select(attrs={'class': 'custom-select mr-sm'}),
                   'amount': NumberInput(attrs={'class': 'form-control mr-sm', 'placeholder': 'Menge in Liter'}),
                   'brewmaster': Select(attrs={'class': 'custom-select mr-sm'})
                   }


class BrewingProtocol(forms.Form):
    comment = forms.CharField(widget=forms.Textarea(
                                attrs={'class': 'form-control',
                                       'rows': 3,
                                       'cols': 30
                                       }), max_length=200, required=False)


class StorageAddItem(ModelForm):
    class Meta:
        model = Storage
        fields = ['name', 'amount', 'type', 'unit']
        widgets = {'unit': Select(attrs={'class': 'custom-select mr-sm'}),
                   'name': TextInput(attrs={'class': 'form-control mr-sm'}),
                   'amount': TextInput(attrs={'class': 'form-control mr-sm'}),
                   'type': Select(attrs={'class': 'custom-select mr-sm'})
                   }


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
        widgets = {'filling': DateTimePickerInput(format='%d.%m.%Y %H:%M'),
                   'content': Select(attrs={'class': 'custom-select mr-sm'}),
                   'notes': TextInput(attrs={'class': 'form-control mr-sm'}),
                   'status': Select(attrs={'class': 'custom-select mr-sm'})
                   }


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
        widgets = {'date': DateTimePickerInput(format='%d.%m.%Y %H:%M'),
                   'plato': NumberInput(attrs={'class': 'form-control mr-sm', 'placeholder': '°Plato'}),
                   'temperature': NumberInput(attrs={'class': 'form-control mr-sm', 'placeholder': '°Celsius'})
                   }


class FinishFermentationForm(ModelForm):
    output = forms.FloatField(required=True, widget=forms.NumberInput(attrs={'class': 'form-control mr-sm', 'placeholder': 'Ausstoß in Liter'}))
    evg = forms.FloatField(required=True, widget=forms.NumberInput(attrs={'class': 'form-control mr-sm', 'placeholder': '°Plato'}))

    class Meta:
        model = Charge
        fields = ['output', 'evg']


class StepForm(ModelForm):
    description = forms.CharField(required=False)
    duration = forms.DurationField(required=False)

    class Meta:
        model = Step
        fields = ['prev', 'title', 'description', 'duration', 'ingredient', 'amount', 'unit']

    def clean(self):
        ingredient = self.cleaned_data.get('ingredient', None)
        amount = self.cleaned_data.get('amount', None)
        unit = self.cleaned_data.get('unit', None)
        if ingredient and not amount:
            self.errors['amount'] = self.error_class(['Mengenangabe wird benötigt!'])
        if amount and not ingredient:
            self.errors['ingredient'] = self.error_class(['Zutat muss gewählt werden.'])
        if amount and not unit:
            self.errors['unit'] = self.error_class(['Einheit wird benötigt!'])

        return self.cleaned_data