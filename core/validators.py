# core/validators.py
import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from datetime import date


def validate_egyptian_phone(value):
    """Validate Egyptian phone number"""
    # Remove any spaces or special characters
    phone = re.sub(r'[^0-9+]', '', value)
    
    # Check Egyptian number patterns
    patterns = [
        r'^01[0-9]{9}$',  # 011, 012, 015, 010
        r'^\+201[0-9]{9}$',  # +201123456789
        r'^00201[0-9]{9}$',  # 00201123456789
    ]
    
    for pattern in patterns:
        if re.match(pattern, phone):
            return value
    
    raise ValidationError(
        _('Invalid Egyptian phone number. Must be like 01123456789 or +201123456789')
    )


def validate_future_date(value):
    """Validate that date is not in the future"""
    if value > date.today():
        raise ValidationError(_('Date cannot be in the future'))


def validate_past_date(value):
    """Validate that date is not in the past"""
    if value < date.today():
        raise ValidationError(_('Date cannot be in the past'))


def validate_positive_amount(value):
    """Validate positive amount"""
    if value <= 0:
        raise ValidationError(_('Amount must be greater than zero'))


def validate_subscription_dates(start_date, end_date):
    """Validate subscription dates"""
    if start_date >= end_date:
        raise ValidationError(_('End date must be after start date'))


def validate_email_domain(value):
    """Validate email domain"""
    allowed_domains = ['gmail.com', 'yahoo.com', 'hotmail.com', 'outlook.com']
    domain = value.split('@')[-1]
    
    # Allow any domain in production
    # if domain not in allowed_domains and not settings.DEBUG:
    #     raise ValidationError(_('Email domain not allowed'))
    
    return value


def validate_password_strength(password):
    """Validate password strength"""
    if len(password) < 8:
        raise ValidationError(_('Password must be at least 8 characters'))
    
    if not re.search(r'[A-Z]', password):
        raise ValidationError(_('Password must contain at least one uppercase letter'))
    
    if not re.search(r'[a-z]', password):
        raise ValidationError(_('Password must contain at least one lowercase letter'))
    
    if not re.search(r'[0-9]', password):
        raise ValidationError(_('Password must contain at least one number'))
    
    if not re.search(r'[!@#$%^&*(),.?":{}|<>]', password):
        raise ValidationError(_('Password must contain at least one special character'))
    
    return password


def validate_qr_token(value):
    """Validate QR token format"""
    if not re.match(r'^[A-Z0-9-]{8,}$', value):
        raise ValidationError(_('Invalid QR token format'))
    
    return value