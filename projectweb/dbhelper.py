"""
Raw-SQL helpers shared by all six apps.

They are the exact Lab 14 pattern, just written once instead of copy-pasted
into every view:

    with connection.cursor() as myCursor:
        myCursor.execute("SELECT ...", [param1, param2])
        columns = [col[0] for col in myCursor.description]
        myFetchData = [dict(zip(columns, row)) for row in myCursor.fetchall()]

    with connection.cursor() as myCursor:
        myCursor.callproc('getorderdetail', [myUserID, ])

IMPORTANT (MySQLdb): when you pass params, a literal % inside the SQL must be
written as %% (e.g. DATE_FORMAT(paid_at, '%%Y-%%m')).  Without params, write %.
"""
from django.db import DatabaseError, connection


def dictfetchall(myCursor):
    """Turn the rows of a cursor into a list of dictionaries (Lab 14)."""
    if myCursor.description is None:
        return []
    columns = [col[0] for col in myCursor.description]
    return [dict(zip(columns, row)) for row in myCursor.fetchall()]


def query_all(sql, params=None):
    """SELECT ... -> list of dict rows."""
    with connection.cursor() as myCursor:
        myCursor.execute(sql, params)
        return dictfetchall(myCursor)


def query_one(sql, params=None):
    """SELECT ... -> first dict row or None."""
    rows = query_all(sql, params)
    return rows[0] if rows else None


def execute(sql, params=None):
    """INSERT / UPDATE / DELETE -> number of affected rows."""
    with connection.cursor() as myCursor:
        myCursor.execute(sql, params)
        return myCursor.rowcount


def call_proc(procname, args=None):
    """CALL a stored procedure (Lab 14 callproc) -> list of dict rows."""
    with connection.cursor() as myCursor:
        myCursor.callproc(procname, args or [])
        return dictfetchall(myCursor)


def call_proc_one(procname, args=None):
    """CALL a BIB procedure that answers with ONE status row:
    {'status': 'SUCCESS' | 'ERROR' | 'DECLINED', 'message': '...', ...}"""
    rows = call_proc(procname, args)
    if rows:
        return rows[0]
    return {'status': 'ERROR', 'message': 'We could not complete your request. Please try again.'}


# Customer-facing wording for every CHECK constraint (MySQL error 3819) and
# UNIQUE key (error 1062) in 01_schema.sql.  The web page never shows the
# constraint name or the raw MySQL text - only these sentences.
CHECK_MESSAGES = {
    'check_role_code': 'Please choose a valid account type.',
    'check_user_active': 'Please choose a valid account status.',
    'check_user_email': 'Please enter a valid e-mail address.',
    'check_user_dob': 'Please enter a valid date of birth.',
    'check_product_category': 'Please choose a valid product category.',
    'check_product_flags': 'Please choose valid product settings.',
    'check_tier_level': 'The plan level must be between 1 and 5.',
    'check_tier_coverage': 'The maximum sum insured must be greater than or equal to the minimum sum insured.',
    'check_tier_premium': 'The base premium must be greater than zero.',
    'check_tier_deductible': 'The deductible must be zero or more and lower than the minimum sum insured.',
    'check_tier_duration': 'The policy term must be between 1 and 24 months.',
    'check_factor_range': 'The range is not valid. Please check the minimum and maximum values.',
    'check_factor_multiplier': 'The factor must be greater than 0 and no more than 5.',
    'check_quote_coverage': 'The sum insured must be greater than zero.',
    'check_quote_age': 'Applicants must be at least 18 years old.',
    'check_quote_risk': 'Please select an underwriting class.',
    'check_quote_premium': 'The premium could not be calculated. Please try again.',
    'check_policy_coverage': 'The sum insured must be greater than zero.',
    'check_policy_remaining': 'The remaining benefit is not valid for this policy.',
    'check_policy_premium': 'The premium must be greater than zero.',
    'check_policy_dates': 'The policy end date must be after the start date.',
    'check_payment_amount': 'The payment amount must be greater than zero.',
    'check_payment_card': 'Please enter a valid 16-digit card number.',
    'check_payment_refund': 'The refund details are incomplete.',
    'check_beneficiary_pct': 'Each benefit share must be more than 0% and no more than 100%.',
    'check_claim_amount': 'The claimed amount must be greater than zero.',
    'check_claim_approved': 'The approved amount cannot exceed the claimed amount.',
    'check_claim_decision': 'Please enter an approved amount for approved claims only.',
    'check_claim_review_time': 'The assessment time cannot be earlier than the submission time.',
    'check_application_flags': 'Please answer the health questions with Yes or No.',
    'check_application_income': 'Please select your monthly income.',
    'check_application_health': 'Please describe your medical history.',
    'check_application_review_time': 'The assessment time cannot be earlier than the submission time.',
}
UNIQUE_MESSAGES = {
    'email_UNIQUE': 'An account with this e-mail address already exists.',
    'product_code_UNIQUE': 'Another product already uses this product code.',
    'product_name_UNIQUE': 'Another product already uses this name.',
    'product_tier_UNIQUE': 'This product already has a plan with that name.',
    'product_level_UNIQUE': 'This product already has a plan at that level.',
    'policy_quote_UNIQUE': 'A policy has already been issued for this quotation.',
    'policy_beneficiary_UNIQUE': 'Each beneficiary can only be listed once.',
    'application_quote_UNIQUE': 'An application has already been submitted for this quotation.',
    'application_number_UNIQUE': 'An application has already been submitted for this quotation.',
}


def db_error_message(error):
    """Customer-friendly text from a MySQL error.

    Our triggers use SIGNAL SQLSTATE '45000' (MySQL error 1644) - their
    MESSAGE_TEXT is already written for customers, so we show it as-is.
    CHECK (3819), UNIQUE (1062) and FOREIGN KEY (1451/1452) errors are
    translated with the dictionaries above.
    """
    code, text = None, str(error)
    if getattr(error, 'args', None) and len(error.args) >= 2:
        code, text = error.args[0], str(error.args[1])
    if code == 1644:
        return text
    if code == 3819:
        for name, message in CHECK_MESSAGES.items():
            if f"'{name}'" in text:
                return message
        return 'Some of the information entered is not valid. Please review the form and try again.'
    if code == 1062:
        for name, message in UNIQUE_MESSAGES.items():
            if name in text:
                return message
        return 'This record already exists.'
    if code == 1451:
        return 'This record is linked to existing policies or claims and cannot be removed.'
    if code == 1452:
        return 'The selected item no longer exists. Please refresh the page and try again.'
    return 'We could not complete your request. Please try again later.'


__all__ = [
    'DatabaseError', 'dictfetchall', 'query_all', 'query_one', 'execute',
    'call_proc', 'call_proc_one', 'db_error_message',
]
