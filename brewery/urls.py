from django.urls import path
from . import views


urlpatterns = [
    path('', views.index, name='index'),
    path('rezepte/', views.recipe, name='recipe'),
    path('spindel/', views.spindel, name='spindel'),
    path('storage/', views.storage, name='storage'),
    path('brewing/', views.brewing, name='brewing'),
    path('rezepte/<int:recipe_id>/', views.recipe_detail, name='recipe_detail'),
]
