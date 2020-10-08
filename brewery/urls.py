from django.urls import path
from . import views


urlpatterns = [
    path('', views.index, name='index'),
    path('spindel/', views.spindel, name='spindel'),
    path('storage/', views.storage, name='storage'),
    path('storage/new/', views.storage_add, name='storage_add'),
    path('storage/<int:s_id>/', views.storage_edit, name='storage_edit'),
    path('brewing/', views.brewing, name='brewing'),
    path('brewing/new/', views.brewing_new, name='brewing_new'),
    path('brewing/<int:charge_id>/', views.protocol, name='protocol'),
    path('recipe/', views.recipe, name='recipe'),
    path('recipe/<int:recipe_id>/', views.recipe_detail, name='recipe_detail'),
    path('recipe/<int:recipe_id>/edit/', views.recipe_edit, name='recipe_edit'),
    path('recipe/new/', views.recipe_new, name='recipe_new')
]
