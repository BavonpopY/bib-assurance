from django.urls import path
from .views import *

urlpatterns = [
  path('signin/', SignIn, name='mySignInPage'),
  path('signout/', SignOut, name='mySignOutPage'),
  path('register/', Register, name='myRegisterPage'),
  path('profile/', Profile, name='myProfilePage'),
  path('beneficiaries/<int:policyID>/', ManageBeneficiaries, name='myBeneficiaryPage'),
  path('users/', UserManagement, name='myUserManagementPage'),
  path('users/add-staff/', AddStaff, name='myAddStaffPage'),
]
