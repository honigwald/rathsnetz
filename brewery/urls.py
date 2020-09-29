from django.urls import path
from . import views


urlpatterns = [
    path('', views.index, name='index'),
    path('spindel/', views.spindel, name='spindel'),
    path('storage/', views.storage, name='storage'),
    path('brewing/', views.brewing, name='brewing'),
    path('recipe/', views.recipe, name='recipe'),
    path('recipe/<int:recipe_id>/', views.recipe_detail, name='recipe_detail'),
    path('recipe/<int:recipe_id>/edit/', views.recipe_edit, name='recipe_edit'),
    path('recipe/new/', views.recipe_new, name='recipe_new')
]
