from django.contrib import admin

from .models import *

# Register your models here.
admin.site.register(Recipe)
admin.site.register(IngredientStorage)
#admin.site.register(Ingredient)
admin.site.register(BeerStorage)
admin.site.register(Charge)
admin.site.register(Fermentation)
admin.site.register(Step)
