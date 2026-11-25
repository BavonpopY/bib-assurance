from django.contrib import admin
from .models import Product, CoverageTier, PremiumFactor, PremiumQuote

# Register your models here (Lab 11: admin.site.register(Product)).
# Optional back office: python manage.py createsuperuser
admin.site.register(Product)
admin.site.register(CoverageTier)
admin.site.register(PremiumFactor)
admin.site.register(PremiumQuote)
