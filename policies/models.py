"""
managed = False  ->  the table is created by database/01_schema.sql (MySQL Workbench),
NOT by "python manage.py migrate".  The model only describes the existing table so
the ORM / Django admin can read and write it (same idea as Lab 11 models.py).
"""
from django.db import models


class Policy(models.Model):
    STATUS_CHOICES = [(s, s) for s in ('Scheduled', 'Active', 'Expired', 'Exhausted', 'Cancelled')]
    policy_id = models.AutoField(primary_key=True)
    policy_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    user = models.ForeignKey('accounts.AppUser', models.RESTRICT, db_column='user_id', related_name='policies')
    tier = models.ForeignKey('catalog.CoverageTier', models.RESTRICT, db_column='tier_id')
    quote = models.OneToOneField('catalog.PremiumQuote', models.SET_NULL, db_column='quote_id', null=True, blank=True)
    coverage_amount = models.DecimalField(max_digits=12, decimal_places=2)
    remaining_coverage = models.DecimalField(max_digits=12, decimal_places=2)
    premium_amount = models.DecimalField(max_digits=10, decimal_places=2)
    start_date = models.DateField()
    end_date = models.DateField()
    policy_status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    created_at = models.DateTimeField()
    cancelled_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'policy'

    def __str__(self) -> str:
        return self.policy_number or f'Policy #{self.policy_id}'
