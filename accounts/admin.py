from django.contrib import admin
from .models import Role, AppUser, PolicyBeneficiary

# Register your models here (Lab 11: admin.site.register(Product)).
# Optional back office: python manage.py createsuperuser
admin.site.register(Role)
admin.site.register(AppUser)
admin.site.register(PolicyBeneficiary)
