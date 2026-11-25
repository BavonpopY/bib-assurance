from django.urls import path
from .views import *

urlpatterns = [
  path('', MyClaims, name='myClaimsPage'),
  path('new/', SubmitClaim, name='mySubmitClaimPage'),
  path('<int:claimID>/', ClaimDetail, name='myClaimDetailPage'),
  path('<int:claimID>/withdraw/', WithdrawClaim, name='myWithdrawClaimPage'),
  path('queue/', ClaimQueue, name='myClaimQueuePage'),
  path('review/<int:claimID>/', ReviewClaim, name='myReviewClaimPage'),
]
