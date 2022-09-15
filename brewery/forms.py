from django import forms
from django.forms import Form, ModelForm, Select, TextInput, NumberInput, NullBooleanField, BooleanField, Textarea
from django.contrib.auth.models import User
from bootstrap_datepicker_plus.widgets import DateTimePickerInput, DatePickerInput
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
    TRUE_FALSE_CHOICES = ((True, 'Aktiv'),
                          (False, 'Inaktiv'))

    class Meta:
        model = Storage
        fields = ['name', 'type', 'amount', 'unit', 'alpha', 'threshold', 'warning', 'danger']
        widgets = {'unit': Select(attrs={'class': 'custom-select mr-sm'}),
                   'name': TextInput(attrs={'class': 'form-control mr-sm'}),
                   'amount': NumberInput(attrs={'class': 'form-control mr-sm'}),
                   'type': Select(attrs={'class': 'custom-select mr-sm'}),
                   'alpha': NumberInput(attrs={'class': 'form-control mr-sm'}),
                   'warning': NumberInput(attrs={'class': 'form-control mr-sm'}),
                   'danger': NumberInput(attrs={'class': 'form-control mr-sm'})
        }
        labels = {'name': 'Bezeichnung',
                  'unit': 'Einheit',
                  'amount': 'Menge',
                  'alpha': 'Alphasäure',
                  'type': 'Obergruppe',
                  'warning': 'Grenzwert Warnung (Gelb)',
                  'danger': 'Grenzwert Kritisch (Rot)'
        }
    threshold = forms.ChoiceField(choices = TRUE_FALSE_CHOICES, widget=forms.Select(), initial='False', label='Warnung bei geringem Bestand')


class AddRecipe(ModelForm):
    class Meta:
        model = Recipe
        fields = ['name', 'hg', 'ng', 'wort', 'ibu', 'boiltime']
        widgets = {'name': TextInput(attrs={'class': 'form-control mr-sm', 'placeholder': 'Rezeptname'}),
                   'hg': NumberInput(attrs={'class': 'form-control mr-sm', 'placeholder': 'Hauptguss [Litern]'}),
                   'ng': NumberInput(attrs={'class': 'form-control mr-sm', 'placeholder': 'Nachguss [Litern]'}),
                   'ibu': NumberInput(attrs={'class': 'form-control mr-sm', 'placeholder': 'Bittere [IBU]'}),
                   'wort': NumberInput(attrs={'class': 'form-control mr-sm', 'placeholder': 'Stammürze in [°Plato]'}),
                   'boiltime': NumberInput(attrs={'class': 'form-control mr-sm', 'placeholder': 'Kochzeit [Minuten]'}),
        }


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
        fields = ['done']


class FermentationProtocolForm(ModelForm):
    class Meta:
        model = FermentationProtocol
        fields = ['temperature', 'plato', 'date']
        widgets = {'date': DateTimePickerInput(format='%d.%m.%Y %H:%M'),
                   'plato': NumberInput(attrs={'class': 'form-control mr-sm', 'placeholder': '°Plato'}),
                   'temperature': NumberInput(attrs={'class': 'form-control mr-sm', 'placeholder': '°Celsius'})
                   }


class FinishFermentationForm(ModelForm):
    output = forms.FloatField(required=True,
                              widget=forms.NumberInput(attrs={'class': 'form-control mr-sm', 'placeholder': 'Ausstoß in Liter'}),
                              label='Ausstoß:')
    restextract = forms.FloatField(required=True,
                           widget=forms.NumberInput(attrs={'class': 'form-control mr-sm', 'placeholder': '°Plato'}),
                           label='Restextrakt:')

    class Meta:
        model = Charge
        fields = ['output', 'restextract']


class KegSelectForm(ModelForm):
    id = forms.ModelMultipleChoiceField(queryset=Keg.objects.filter(content=None),
                                        required=False,
                                        label = 'Schon abgefüllt? Wähle hier die KEGs:')
    class Meta:
        model = Keg
        fields = ['id']


class StepForm(ModelForm):
    class Meta:
        model = Step
        fields = ['prev', 'category', 'title', 'description', 'duration', 'ingredient', 'amount', 'unit']
        widgets = {'description': Textarea(attrs={'class': 'form-control mr-sm', 'rows': 4})}
        labels = {'prev': 'Vorgänger (wenn leer, dann als 1. Schritt einfügen)',
                  'category': 'Kategorie',
                  'titel': 'Titel',
                  'description': 'Beschreibung',
                  'duration': 'Dauer',
                  'ingredient': 'Zutat',
                  'amount': 'Menge',
                  'unit': 'Einheit'
        }

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
