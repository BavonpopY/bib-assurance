from django.urls import path
from .views import *

urlpatterns = [
  path('<int:quoteID>/', Checkout, name='myCheckoutPage'),
  path('success/<int:policyID>/', CheckoutSuccess, name='myCheckoutSuccessPage'),
  path('payments/', PaymentHistory, name='myPaymentHistoryPage'),
  path('log/', CheckoutLog, name='myCheckoutLogPage'),
  path('application/<int:quoteID>/', ApplicationForm, name='myApplicationFormPage'),
  path('applications/', MyApplications, name='myApplicationsPage'),
  path('applications/<int:applicationID>/', ApplicationDetail, name='myApplicationDetailPage'),
  path('underwriting/', ApplicationQueue, name='myApplicationQueuePage'),
  path('underwriting/<int:applicationID>/', ReviewApplication, name='myReviewApplicationPage'),
]
