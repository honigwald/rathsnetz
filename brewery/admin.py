from django.contrib import admin

from .models import (
    Recipe,
    Step,
    Charge,
    RecipeProtocol,
    Keg,
    Hint,
    FermentationProtocol,
    HopCalculation,
    BeerOutput,
    Preparation,
    Storage,
    PreparationProtocol,
    Unit,
    Type,
    Category,
    Account,
)

# Register your models here.
admin.site.register(Recipe)
admin.site.register(Preparation)
admin.site.register(Storage)
admin.site.register(RecipeProtocol)
admin.site.register(Hint)
admin.site.register(PreparationProtocol)
admin.site.register(Keg)
admin.site.register(Charge)
admin.site.register(FermentationProtocol)
admin.site.register(Step)
admin.site.register(Unit)
admin.site.register(Type)
admin.site.register(Category)
admin.site.register(HopCalculation)
admin.site.register(BeerOutput)
admin.site.register(Account)
