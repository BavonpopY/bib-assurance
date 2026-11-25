from django.contrib import admin
from .models import Payment, CheckoutLog

# Register your models here (Lab 11: admin.site.register(Product)).
# Optional back office: python manage.py createsuperuser
admin.site.register(Payment)
admin.site.register(CheckoutLog)
