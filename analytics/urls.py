from django.urls import path
from .views import *

urlpatterns = [
  path('', Dashboard, name='myDashboardPage'),
  path('reports/', Reports, name='myReportsPage'),
]
