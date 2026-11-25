"""
managed = False  ->  the table is created by database/01_schema.sql (MySQL Workbench),
NOT by "python manage.py migrate".  The model only describes the existing table so
the ORM / Django admin can read and write it (same idea as Lab 11 models.py).
"""
from django.db import models


class Product(models.Model):
    CATEGORY_CHOICES = [
        ('Health', 'Health'), ('Critical Illness', 'Critical Illness'), ('Life', 'Life'),
        ('Personal Accident', 'Personal Accident'), ('Retirement', 'Retirement'),
    ]
    product_id = models.AutoField(primary_key=True)
    product_code = models.CharField(max_length=20, unique=True)
    product_name = models.CharField(max_length=100, unique=True)
    tagline = models.CharField(max_length=160)
    description = models.TextField()
    category = models.CharField(max_length=40, choices=CATEGORY_CHOICES)
    # LabExtra used ImageField; we store the same kind of relative path in a VARCHAR
    thumbnail_path = models.CharField(max_length=255, null=True, blank=True)
    requires_beneficiary = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'product'

    def __str__(self) -> str:
        return self.product_name


class CoverageTier(models.Model):
    tier_id = models.AutoField(primary_key=True)
    product = models.ForeignKey(Product, models.CASCADE, db_column='product_id')
    tier_name = models.CharField(max_length=50)
    tier_level = models.SmallIntegerField()
    min_coverage = models.DecimalField(max_digits=12, decimal_places=2)
    max_coverage = models.DecimalField(max_digits=12, decimal_places=2)
    base_annual_premium = models.DecimalField(max_digits=10, decimal_places=2)
    deductible = models.DecimalField(max_digits=10, decimal_places=2)
    duration_months = models.PositiveSmallIntegerField()
    perks = models.CharField(max_length=255, null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'coverage_tier'

    def __str__(self) -> str:
        return f'{self.product} - {self.tier_name}'


class PremiumFactor(models.Model):
    factor_id = models.AutoField(primary_key=True)
    product = models.ForeignKey(Product, models.CASCADE, db_column='product_id', null=True, blank=True)
    factor_type = models.CharField(max_length=4, choices=[('AGE', 'AGE'), ('RISK', 'RISK')])
    range_min = models.SmallIntegerField()
    range_max = models.SmallIntegerField()
    multiplier = models.DecimalField(max_digits=5, decimal_places=3)
    label = models.CharField(max_length=60)

    class Meta:
        managed = False
        db_table = 'premium_factor'

    def __str__(self) -> str:
        return f'{self.factor_type} {self.range_min}-{self.range_max}: x{self.multiplier} ({self.label})'


class PremiumQuote(models.Model):
    quote_id = models.AutoField(primary_key=True)
    user = models.ForeignKey('accounts.AppUser', models.CASCADE, db_column='user_id')
    tier = models.ForeignKey(CoverageTier, models.CASCADE, db_column='tier_id')
    coverage_amount = models.DecimalField(max_digits=12, decimal_places=2)
    insured_age = models.PositiveSmallIntegerField()
    risk_level = models.PositiveSmallIntegerField()
    age_multiplier = models.DecimalField(max_digits=5, decimal_places=3)
    risk_multiplier = models.DecimalField(max_digits=5, decimal_places=3)
    quoted_premium = models.DecimalField(max_digits=10, decimal_places=2)
    quote_status = models.CharField(max_length=10)
    created_at = models.DateTimeField()
    expires_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'premium_quote'

    def __str__(self) -> str:
        return f'Quote #{self.quote_id}'
