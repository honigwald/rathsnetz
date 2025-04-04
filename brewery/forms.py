from django import forms
from django.forms import (
    Form,
    ModelForm,
    Select,
    TextInput,
    NumberInput,
    Textarea,
)
from bootstrap_datepicker_plus.widgets import DateTimePickerInput

from brewery.models import Recipe
from brewery.models import Charge, PendingPreparation
from brewery.models import RecipeBrewStep
from brewery.models import Keg
from brewery.models import FermentationProtocolStep
from brewery.models import Preparation
from brewery.models import Storage


class BrewingCharge(ModelForm):
    class Meta:
        model = Charge
        fields = ["brewmaster", "amount", "recipe"]
        widgets = {
            "recipe": Select(attrs={"class": "custom-select mr-sm"}),
            "amount": NumberInput(
                attrs={"class": "form-control mr-sm", "placeholder": "Menge in Liter"}
            ),
            "brewmaster": Select(attrs={"class": "custom-select mr-sm"}),
        }
        labels = {
            "recipe": "Rezept",
            "amount": "Menge",
            "brewmaster": "Braumeister",
        }

    CHOICES = [
        ("Y", "Ja"),
        ("N", "Nein"),
    ]
    dsud_active = forms.ChoiceField(
        choices=CHOICES, widget=forms.RadioSelect, label="Doppelsud", initial="N"
    )


class BrewingProtocol(forms.Form):
    comment = forms.CharField(
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3, "cols": 30}),
        max_length=200,
        required=False,
    )


class StorageAddItem(ModelForm):
    TRUE_FALSE_CHOICES = ((True, "Aktiv"), (False, "Inaktiv"))

    class Meta:
        model = Storage
        fields = [
            "name",
            "type",
            "amount",
            "unit",
            "alpha",
            "threshold",
            "warning",
            "danger",
        ]
        widgets = {
            "unit": Select(attrs={"class": "custom-select mr-sm"}),
            "name": TextInput(attrs={"class": "form-control mr-sm"}),
            "amount": NumberInput(attrs={"class": "form-control mr-sm"}),
            "type": Select(attrs={"class": "custom-select mr-sm"}),
            "alpha": NumberInput(attrs={"class": "form-control mr-sm"}),
            "warning": NumberInput(attrs={"class": "form-control mr-sm"}),
            "danger": NumberInput(attrs={"class": "form-control mr-sm"}),
        }
        labels = {
            "name": "Bezeichnung",
            "unit": "Einheit",
            "amount": "Menge",
            "alpha": "Alphasäure",
            "type": "Obergruppe",
            "warning": "Grenzwert Warnung (Gelb)",
            "danger": "Grenzwert Kritisch (Rot)",
        }

    threshold = forms.ChoiceField(
        choices=TRUE_FALSE_CHOICES,
        widget=forms.Select(),
        initial="False",
        label="Warnung bei geringem Bestand",
    )


class AddRecipe(ModelForm):
    class Meta:
        model = Recipe
        fields = ["name", "hg", "ng", "wort", "ibu", "boiltime"]
        widgets = {
            "name": TextInput(
                attrs={"class": "form-control mr-sm", "placeholder": "Rezeptname"}
            ),
            "hg": NumberInput(
                attrs={
                    "class": "form-control mr-sm",
                    "placeholder": "Hauptguss [Litern]",
                }
            ),
            "ng": NumberInput(
                attrs={
                    "class": "form-control mr-sm",
                    "placeholder": "Nachguss [Litern]",
                }
            ),
            "ibu": NumberInput(
                attrs={"class": "form-control mr-sm", "placeholder": "Bittere [IBU]"}
            ),
            "wort": NumberInput(
                attrs={
                    "class": "form-control mr-sm",
                    "placeholder": "Stammürze in [°Plato]",
                }
            ),
            "boiltime": NumberInput(
                attrs={
                    "class": "form-control mr-sm",
                    "placeholder": "Kochzeit [Minuten]",
                }
            ),
        }


class EditRecipe(ModelForm):
    class Meta:
        model = RecipeBrewStep
        exclude = ("recipe",)


class EditKegContent(ModelForm):
    class Meta:
        model = Keg
        fields = ["content", "status", "notes", "filling"]
        widgets = {
            "filling": DateTimePickerInput(format="%d.%m.%Y %H:%M"),
            "content": Select(attrs={"class": "custom-select mr-sm"}),
            "notes": TextInput(attrs={"class": "form-control mr-sm"}),
            "status": Select(attrs={"class": "custom-select mr-sm"}),
        }


class SelectPreparation(Form):
    preparation = forms.ModelMultipleChoiceField(
        queryset=Preparation.objects.all(), required=False
    )


class PendingPreparationForm(ModelForm):
    class Meta:
        model = PendingPreparation
        fields = ["done"]


class FermentationProtocolForm(ModelForm):
    class Meta:
        model = FermentationProtocolStep
        fields = ["temperature", "plato", "date"]
        widgets = {
            "date": DateTimePickerInput(format="%d.%m.%Y %H:%M"),
            "plato": NumberInput(
                attrs={"class": "form-control mr-sm", "placeholder": "°Plato"}
            ),
            "temperature": NumberInput(
                attrs={"class": "form-control mr-sm", "placeholder": "°Celsius"}
            ),
        }


class FinishFermentationForm(ModelForm):
    output = forms.FloatField(
        required=True,
        widget=forms.NumberInput(
            attrs={"class": "form-control mr-sm", "placeholder": "Ausstoß in Liter"}
        ),
        label="Ausstoß:",
    )
    restextract = forms.FloatField(
        required=True,
        widget=forms.NumberInput(
            attrs={"class": "form-control mr-sm", "placeholder": "°Plato"}
        ),
        label="Restextrakt:",
    )

    class Meta:
        model = Charge
        fields = ["output", "restextract"]


class KegSelectForm(ModelForm):
    id = forms.ModelMultipleChoiceField(
        queryset=Keg.objects.filter(content=None),
        required=False,
        label="Schon abgefüllt? Wähle hier die KEGs:",
    )

    class Meta:
        model = Keg
        fields = ["id"]


class StepPredecessorForm(ModelForm):
    preds = forms.ModelChoiceField(
        queryset=RecipeBrewStep.objects.none(),  # filter(content=None),
        required=False,
        label="Vorgänger",
    )

    class Meta:
        model = RecipeBrewStep
        fields = ["id", "preds"]

    def __init__(self, *args, **kwargs):
        # Pop the name filter from kwargs (default to None if not provided)
        recipe = kwargs.pop("recipe", None)
        step_id = kwargs.pop("step_id", None)
        super().__init__(*args, **kwargs)

        # Set the queryset for the filtered field based on the dynamic name_filter
        if recipe is not None:
            self.fields["preds"].queryset = RecipeBrewStep.objects.filter(
                rname=recipe
            ).exclude(id=step_id)
        else:
            # If no filter is provided, set an empty queryset or a default queryset
            self.fields["preds"].queryset = RecipeBrewStep.objects.all()


class StepForm(ModelForm):
    class Meta:
        model = RecipeBrewStep
        fields = [
            "category",
            "title",
            "description",
            "duration",
            "ingredient",
            "amount",
            "unit",
        ]
        widgets = {
            "description": Textarea(attrs={"class": "form-control mr-sm", "rows": 4})
        }
        labels = {
            "category": "Kategorie",
            "titel": "Titel",
            "description": "Beschreibung",
            "duration": "Dauer",
            "ingredient": "Zutat",
            "amount": "Menge",
            "unit": "Einheit",
        }

    def clean(self):
        ingredient = self.cleaned_data.get("ingredient", None)
        amount = self.cleaned_data.get("amount", None)
        unit = self.cleaned_data.get("unit", None)
        if ingredient and not amount:
            self.errors["amount"] = self.error_class(["Mengenangabe wird benötigt!"])
        if amount and not ingredient:
            self.errors["ingredient"] = self.error_class(["Zutat muss gewählt werden."])
        if amount and not unit:
            self.errors["unit"] = self.error_class(["Einheit wird benötigt!"])

        return self.cleaned_data


class InitFermentationForm(ModelForm):
    CHOICES = [("True", "Ja"), ("False", "Nein")]
    use_ispindel = forms.ChoiceField(
        choices=CHOICES,
        widget=forms.RadioSelect,
        label="Willst du die iSpindel benutzen?",
    )
    reached_wort = forms.FloatField(
        required=True,
        widget=forms.NumberInput(
            attrs={"class": "form-control mr-sm", "placeholder": "°Plato"}
        ),
        label="Erreichte Stammwürze:",
    )

    class Meta:
        model = Charge
        fields = ["reached_wort"]
