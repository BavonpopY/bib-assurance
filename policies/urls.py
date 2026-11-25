from django.urls import path
from .views import *

urlpatterns = [
  path('', MyPolicies, name='myPoliciesPage'),
  path('<int:policyID>/', PolicyDetail, name='myPolicyDetailPage'),
  path('<int:policyID>/cancel/', CancelPolicy, name='myCancelPolicyPage'),
  path('all/', AllPolicies, name='myAllPoliciesPage'),
]
