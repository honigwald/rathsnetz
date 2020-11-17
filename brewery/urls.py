from django.urls import path
from . import views


urlpatterns = [
    path('', views.index, name='index'),
    path('fermentation/<int:cid>', views.fermentation, name='fermentation'),
    path('keg/', views.keg, name='keg'),
    path('storage/', views.storage, name='storage'),
    path('storage/add/', views.storage_add, name='storage_add'),
    path('storage/<int:s_id>/', views.storage_edit, name='storage_edit'),
    path('brewing/', views.brewing_overview, name='brewing_overview'),
    path('brewing/add/', views.brewing_add, name='brewing_add'),
    path('brewing/protocol/<int:cid>/', views.protocol, name='protocol'),
    path('brewing/<int:cid>/', views.brewing, name='brewing'),
    path('recipe/', views.recipe, name='recipe'),
    path('recipe/<int:recipe_id>/', views.recipe_detail, name='recipe_detail'),
    #path('recipe/<int:recipe_id>/edit/', views.recipe_edit, name='recipe_edit'),
    path('recipe/<int:recipe_id>/steps/', views.recipe_steps, name='recipe_steps'),
    path('recipe/<int:recipe_id>/steps/<int:step_id>', views.step_edit, name='step_edit'),
    path('recipe/<int:recipe_id>/steps/add', views.step_edit, name='step_add'),
    path('recipe/add/', views.recipe_add, name='recipe_add')
]
