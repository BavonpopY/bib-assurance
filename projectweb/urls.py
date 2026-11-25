"""
URL configuration for projectweb project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/4.2/topics/http/urls/
Same pattern as myfirstweb/urls.py: every app owns its own urls.py.
"""
from django.contrib import admin
from django.urls import path, include

#เพิ่ม Static Config สําหรับ Image Field
from django.contrib.staticfiles.urls import static, staticfiles_urlpatterns
from . import settings

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('catalog.urls')),
    path('accounts/', include('accounts.urls')),
    path('checkout/', include('checkout.urls')),
    path('policies/', include('policies.urls')),
    path('claims/', include('claims.urls')),
    path('analytics/', include('analytics.urls')),
]

urlpatterns += staticfiles_urlpatterns()
urlpatterns += static(settings.MEDIA_URL,
document_root=settings.MEDIA_ROOT)
