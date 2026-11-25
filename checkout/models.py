"""
managed = False  ->  the table is created by database/01_schema.sql (MySQL Workbench),
NOT by "python manage.py migrate".  The model only describes the existing table so
the ORM / Django admin can read and write it (same idea as Lab 11 models.py).
"""
from django.db import models


class Payment(models.Model):
    payment_id = models.AutoField(primary_key=True)
    policy = models.ForeignKey('policies.Policy', models.RESTRICT, db_column='policy_id')
    user = models.ForeignKey('accounts.AppUser', models.RESTRICT, db_column='user_id')
    amount = models.DecimalField(max_digits=10, decimal_places=2)
    payment_method = models.CharField(max_length=12)
    card_last4 = models.CharField(max_length=4, null=True, blank=True)
    payment_status = models.CharField(max_length=10)
    transaction_ref = models.CharField(max_length=40, unique=True)
    paid_at = models.DateTimeField()
    refunded_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'payment'

    def __str__(self) -> str:
        return self.transaction_ref


class CheckoutLog(models.Model):
    log_id = models.AutoField(primary_key=True)
    user = models.ForeignKey('accounts.AppUser', models.CASCADE, db_column='user_id')
    quote = models.ForeignKey('catalog.PremiumQuote', models.SET_NULL, db_column='quote_id', null=True, blank=True)
    policy = models.ForeignKey('policies.Policy', models.SET_NULL, db_column='policy_id', null=True, blank=True)
    amount = models.DecimalField(max_digits=10, decimal_places=2, null=True, blank=True)
    payment_method = models.CharField(max_length=20, null=True, blank=True)
    card_last4 = models.CharField(max_length=4, null=True, blank=True)
    result = models.CharField(max_length=10)
    message = models.CharField(max_length=255)
    attempted_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'checkout_log'

    def __str__(self) -> str:
        return f'{self.result}: {self.message}'


class UnderwritingApplication(models.Model):
    """Application a customer submits before paying (reviewed by an officer)."""
    INCOME_CHOICES = [
        ('Below 15,000', 'Below 15,000'), ('15,000-30,000', '15,000-30,000'), ('30,001-50,000', '30,001-50,000'),
        ('50,001-100,000', '50,001-100,000'), ('Above 100,000', 'Above 100,000'),
    ]
    application_id = models.AutoField(primary_key=True)
    application_number = models.CharField(max_length=20, unique=True, null=True, blank=True)
    quote = models.OneToOneField('catalog.PremiumQuote', models.CASCADE, db_column='quote_id')
    user = models.ForeignKey('accounts.AppUser', models.CASCADE, db_column='user_id', related_name='applications')
    occupation = models.CharField(max_length=100)
    employer = models.CharField(max_length=120, null=True, blank=True)
    monthly_income = models.CharField(max_length=30, choices=INCOME_CHOICES)
    is_smoker = models.IntegerField(default=0)
    has_medical_history = models.IntegerField(default=0)
    health_details = models.CharField(max_length=500, null=True, blank=True)
    app_status = models.CharField(max_length=10, default='Pending')
    reviewed_by = models.ForeignKey('accounts.AppUser', models.SET_NULL, db_column='reviewed_by',
                                    null=True, blank=True, related_name='reviewed_applications')
    review_note = models.CharField(max_length=255, null=True, blank=True)
    submitted_at = models.DateTimeField()
    reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        managed = False
        db_table = 'underwriting_application'

    def __str__(self) -> str:
        return self.application_number or f'Application {self.application_id}'


class ApplicationDocument(models.Model):
    document_id = models.AutoField(primary_key=True)
    application = models.ForeignKey(UnderwritingApplication, models.CASCADE, db_column='application_id')
    document_type = models.CharField(max_length=12)
    image_path = models.CharField(max_length=255)
    caption = models.CharField(max_length=160, null=True, blank=True)
    uploaded_at = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'application_document'

    def __str__(self) -> str:
        return self.caption or self.image_path
