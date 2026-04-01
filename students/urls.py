from django.contrib import admin
from django.urls import path, include
from . import views

urlpatterns = [
path('import/', views.import_sinh_vien, name='import_sinh_vien'),
path('tra-cuu/', views.tra_cuu, name='tra_cuu'),
]