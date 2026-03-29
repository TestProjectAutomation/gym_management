# core/utils.py
import uuid
import random
import string
from datetime import datetime, timedelta
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from decimal import Decimal
import logging

logger = logging.getLogger(__name__)


def generate_unique_code(prefix='', length=8):
    """Generate unique code for various purposes"""
    code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=length))
    return f"{prefix}{code}" if prefix else code


def generate_receipt_number():
    """Generate unique receipt number"""
    date_str = datetime.now().strftime('%Y%m%d')
    unique_id = uuid.uuid4().hex[:6].upper()
    return f"INV-{date_str}-{unique_id}"


def calculate_age(birth_date):
    """Calculate age from birth date"""
    if not birth_date:
        return None
    today = timezone.now().date()
    return today.year - birth_date.year - (
        (today.month, today.day) < (birth_date.month, birth_date.day)
    )


def format_currency(amount, currency='EGP'):
    """Format currency amount"""
    if currency == 'EGP':
        return f"EGP {amount:,.2f}"
    elif currency == 'USD':
        return f"${amount:,.2f}"
    elif currency == 'EUR':
        return f"€{amount:,.2f}"
    return f"{amount:,.2f} {currency}"


def get_date_range(range_type='week'):
    """Get date range for reports"""
    today = timezone.now().date()
    
    if range_type == 'day':
        start_date = today
        end_date = today
    elif range_type == 'week':
        start_date = today - timedelta(days=today.weekday())
        end_date = start_date + timedelta(days=6)
    elif range_type == 'month':
        start_date = today.replace(day=1)
        end_date = (start_date + timedelta(days=32)).replace(day=1) - timedelta(days=1)
    elif range_type == 'year':
        start_date = today.replace(month=1, day=1)
        end_date = today.replace(month=12, day=31)
    else:
        start_date = today - timedelta(days=30)
        end_date = today
    
    return start_date, end_date


def send_email_notification(subject, message, recipient_list):
    """Send email notification"""
    try:
        send_mail(
            subject=subject,
            message=message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=recipient_list,
            fail_silently=False,
        )
        logger.info(f"Email sent to {recipient_list}")
        return True
    except Exception as e:
        logger.error(f"Failed to send email: {e}")
        return False


def calculate_percentage(value, total):
    """Calculate percentage"""
    if not total:
        return 0
    return (value / total) * 100


def dict_diff(dict1, dict2):
    """Get difference between two dictionaries"""
    diff = {}
    for key in set(dict1.keys()) | set(dict2.keys()):
        if dict1.get(key) != dict2.get(key):
            diff[key] = {
                'old': dict1.get(key),
                'new': dict2.get(key)
            }
    return diff


def chunk_list(lst, chunk_size):
    """Split list into chunks"""
    for i in range(0, len(lst), chunk_size):
        yield lst[i:i + chunk_size]


class CacheKey:
    """Cache key constants"""
    DASHBOARD_STATS = 'dashboard_stats_{gym_id}'
    MEMBER_ATTENDANCE = 'member_attendance_{member_id}_{days}'
    GYM_SETTINGS = 'gym_settings_{gym_id}'
    SUBSCRIPTION_STATS = 'subscription_stats_{gym_id}'
    
    @classmethod
    def format(cls, key, **kwargs):
        return key.format(**kwargs)


def generate_qr_data(member_id, gym_id):
    """Generate QR code data"""
    data = {
        'type': 'member_checkin',
        'member_id': str(member_id),
        'gym_id': str(gym_id),
        'timestamp': datetime.now().isoformat()
    }
    # You can add encryption here if needed
    return str(data)


def validate_phone_number(phone):
    """Validate phone number format"""
    # Remove any spaces or special characters
    phone = ''.join(filter(str.isdigit, phone))
    
    # Check Egyptian phone numbers
    if phone.startswith('01') and len(phone) == 11:
        return True
    
    # Check international format
    if phone.startswith('20') and len(phone) == 12:
        return True
    
    return False