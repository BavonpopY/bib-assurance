"""
managed = False  ->  the table is created by database/01_schema.sql (MySQL Workbench),
NOT by "python manage.py migrate".  The model only describes the existing table so
the ORM / Django admin can read and write it (same idea as Lab 11 models.py).
"""
from django.db import models


class Claim(models.Model):
    claim_id = models.AutoField(primary_key=True)
    claim_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    policy = models.ForeignKey('policies.Policy', models.RESTRICT, db_column='policy_id')
    incident_date = models.DateField()
    incident_title = models.CharField(max_length=120)
    incident_description = models.TextField()
    claimed_amount = models.DecimalField(max_digits=12, decimal_places=2)
    approved_amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    claim_status = models.CharField(max_length=10)
    reviewed_by = models.ForeignKey('accounts.AppUser', models.SET_NULL, db_column='reviewed_by',
                                    null=True, blank=True, related_name='reviewed_claims')
    review_note = models.CharField(max_length=255, null=True, blank=True)
    submitted_at = models.DateTimeField()
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'claim'

    def __str__(self) -> str:
        return self.claim_number or f'Claim #{self.claim_id}'


class ClaimEvidence(models.Model):
    evidence_id = models.AutoField(primary_key=True)
    claim = models.ForeignKey(Claim, models.CASCADE, db_column='claim_id')
    image_path = models.CharField(max_length=255)
    caption = models.CharField(max_length=160, null=True, blank=True)
    uploaded_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'claim_evidence'


class ClaimStatusAudit(models.Model):
    audit_id = models.AutoField(primary_key=True)
    claim = models.ForeignKey(Claim, models.CASCADE, db_column='claim_id')
    policy_id = models.IntegerField()
    old_status = models.CharField(max_length=20, null=True, blank=True)
    new_status = models.CharField(max_length=20)
    amount = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    remaining_before = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    remaining_after = models.DecimalField(max_digits=12, decimal_places=2, null=True, blank=True)
    changed_by = models.IntegerField(null=True, blank=True)
    actiontype = models.CharField(max_length=50)
    changedate = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'claim_status_audit'
