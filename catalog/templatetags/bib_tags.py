"""Small template filters shared by every app.

    {% load bib_tags %}
    <span class="badge {{ policy.live_status|status_badge }}">{{ policy.live_status }}</span>
    {{ amount|thb }}            ->  ฿12,500.00
    {{ amount|thb:0 }}          ->  ฿12,500
"""
from decimal import Decimal, InvalidOperation

from django import template

register = template.Library()

# Bootstrap 5.3 contextual badge classes for every status used in BIB
STATUS_CLASSES = {
    'Active': 'text-bg-success', 'Scheduled': 'text-bg-info', 'Expired': 'text-bg-secondary',
    'Exhausted': 'text-bg-warning', 'Cancelled': 'text-bg-dark',
    'Pending': 'text-bg-warning', 'Approved': 'text-bg-success', 'Rejected': 'text-bg-danger',
    'Paid': 'text-bg-success', 'Refunded': 'text-bg-secondary',
    'SUCCESS': 'text-bg-success', 'DECLINED': 'text-bg-danger', 'ERROR': 'text-bg-secondary',
    'Open': 'text-bg-primary', 'Converted': 'text-bg-success',
    'Complete': 'text-bg-success', 'Action needed': 'text-bg-danger', 'Optional': 'text-bg-light',
    'Incomplete': 'text-bg-warning', 'In review': 'text-bg-warning', 'Declined': 'text-bg-danger',
}

# Wording shown to people (the database keeps its own status codes)
STATUS_LABELS = {
    'SUCCESS': 'Successful', 'DECLINED': 'Declined', 'ERROR': 'Not completed',
    'Pending': 'Under review', 'Rejected': 'Declined', 'Scheduled': 'Upcoming',
    'Action needed': 'Action required', 'Converted': 'Purchased', 'Open': 'Awaiting documents',
    'BankTransfer': 'Bank transfer', 'Card': 'Credit / debit card', 'PromptPay': 'PromptPay',
}


@register.filter
def status_badge(value):
    return STATUS_CLASSES.get(str(value), 'text-bg-secondary')


@register.filter
def status_label(value):
    return STATUS_LABELS.get(str(value), value)


@register.filter
def thb(value, places=2):
    try:
        number = Decimal(value)
    except (InvalidOperation, TypeError, ValueError):
        return value
    places = int(places)
    return f'฿{number:,.{places}f}'


@register.filter
def get_item(mapping, key):
    """{{ counts|get_item:status }} - read a dictionary with a variable key."""
    try:
        return mapping.get(key, 0)
    except AttributeError:
        return 0


@register.filter
def initials(name):
    """'Somchai Jaidee' -> 'SJ' (used when a person has no profile photo)."""
    parts = str(name or '').split()
    return ''.join(p[0] for p in parts[:2]).upper() or '?'


@register.filter
def pct_class(value):
    """Bootstrap progress-bar colour for a percentage of benefit used."""
    try:
        value = float(value)
    except (TypeError, ValueError):
        return 'bg-primary'
    if value >= 100:
        return 'bg-secondary'
    if value >= 75:
        return 'bg-warning'
    return 'bg-primary'


@register.filter
def split_perks(value):
    """'A · B · C' -> ['A', 'B', 'C'] (plan benefits are stored as one line)."""
    return [p.strip() for p in str(value or '').split('·') if p.strip()]
