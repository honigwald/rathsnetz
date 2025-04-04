from django.contrib import admin

# Import models
from brewery.models import Charge, PendingPreparation
from .models.recipe import Recipe
from .models.step import BrewProtocolStep, RecipeBrewStep

# from .models.protocol import BrewProtocol, FermentationProtocol, PreparationProtocol
from brewery.models import BrewProtocol, FermentationProtocol
from .models.keg import Keg
from .models.hint import Hint
from .models.hop_calculation import HopCalculation
from .models.beer_output import BeerOutput
from .models.account import Account
from .models.preparation import Preparation
from .models.storage import Storage
from .models.unit import Unit
from .models.type import Type
from .models.category import Category
from brewery.models import FermentationProtocolStep

# Register models
admin.site.register(Recipe)
admin.site.register(Preparation)
admin.site.register(Storage)
admin.site.register(BrewProtocol)
admin.site.register(Hint)
admin.site.register(PendingPreparation)
admin.site.register(Keg)
admin.site.register(Charge)
admin.site.register(FermentationProtocol)
admin.site.register(FermentationProtocolStep)
admin.site.register(BrewProtocolStep)
admin.site.register(RecipeBrewStep)
admin.site.register(Unit)
admin.site.register(Type)
admin.site.register(Category)
admin.site.register(HopCalculation)
admin.site.register(BeerOutput)
admin.site.register(Account)
