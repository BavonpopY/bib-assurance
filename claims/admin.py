from django.contrib import admin
from .models import Claim, ClaimEvidence, ClaimStatusAudit

# Register your models here (Lab 11: admin.site.register(Product)).
# Optional back office: python manage.py createsuperuser
admin.site.register(Claim)
admin.site.register(ClaimEvidence)
admin.site.register(ClaimStatusAudit)
