from django.urls import path
from .views import *

urlpatterns = [
  path('', Home, name='myHomePage'),
  path('about/', AboutBIB, name='myAboutPage'),
  path('products/', ProductList, name='myProductListPage'),
  path('products/<int:productID>/', ProductDetail, name='myProductDetailPage'),
  path('premium-preview/', PremiumPreview, name='myPremiumPreview'),
  path('quote/', CreateQuote, name='myCreateQuotePage'),
  path('quote/<int:quoteID>/', QuoteDetail, name='myQuoteDetailPage'),
  # admin (Lab 13 pattern)
  path('manage/products/', ProductMain, name='myProductMainPage'),
  path('manage/products/add/', AddProduct, name='myAddProductPage'),
  path('manage/products/<int:productID>/', UpdateProduct, name='myUpdateProductPage'),
  path('manage/products/<int:productID>/tiers/', ManageTiers, name='myManageTiersPage'),
  path('manage/tiers/<int:tierID>/', UpdateTier, name='myUpdateTierPage'),
  path('manage/factors/', ManageFactors, name='myManageFactorsPage'),
]
