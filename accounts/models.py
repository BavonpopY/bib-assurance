"""
managed = False  ->  the table is created by database/01_schema.sql (MySQL Workbench),
NOT by "python manage.py migrate".  The model only describes the existing table so
the ORM / Django admin can read and write it (same idea as Lab 11 models.py).
"""
from django.db import models


class Role(models.Model):
    role_id = models.AutoField(primary_key=True)
    role_code = models.CharField(max_length=20, unique=True)
    role_name = models.CharField(max_length=50)

    class Meta:
        managed = False
        db_table = 'role'

    def __str__(self) -> str:
        return self.role_name


class AppUser(models.Model):
    user_id = models.AutoField(primary_key=True)
    role = models.ForeignKey(Role, models.RESTRICT, db_column='role_id')
    email = models.CharField(max_length=120, unique=True)
    password_hash = models.CharField(max_length=255)
    first_name = models.CharField(max_length=60)
    last_name = models.CharField(max_length=60)
    phone = models.CharField(max_length=20, null=True, blank=True)
    date_of_birth = models.DateField(null=True, blank=True)
    avatar_path = models.CharField(max_length=255, null=True, blank=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField()
    last_login_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'app_user'

    def __str__(self) -> str:
        return f'{self.first_name} {self.last_name} <{self.email}>'


class PolicyBeneficiary(models.Model):
    beneficiary_id = models.AutoField(primary_key=True)
    policy = models.ForeignKey('policies.Policy', models.CASCADE, db_column='policy_id')
    full_name = models.CharField(max_length=120)
    relationship = models.CharField(max_length=40)
    allocation_pct = models.DecimalField(max_digits=5, decimal_places=2)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'policy_beneficiary'

    def __str__(self) -> str:
        return f'{self.full_name} ({self.allocation_pct}%)'
