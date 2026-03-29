# core/tasks.py
from celery import shared_task
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from datetime import timedelta
import logging

from .models import Subscription, MemberProfile, GymSettings, Attendance
from .services import SubscriptionService, DashboardService

logger = logging.getLogger(__name__)


@shared_task
def check_expired_subscriptions():
    """Check and mark expired subscriptions"""
    try:
        count = SubscriptionService.check_expired_subscriptions()
        logger.info(f"Expired {count} subscriptions")
        return count
    except Exception as e:
        logger.error(f"Failed to check expired subscriptions: {e}")
        return 0


@shared_task
def send_subscription_expiry_notifications():
    """Send notifications for subscriptions expiring soon"""
    days_before = [3, 1]  # Send 3 days and 1 day before expiry
    today = timezone.now().date()
    
    for days in days_before:
        expiry_date = today + timedelta(days=days)
        
        subscriptions = Subscription.objects.filter(
            status=Subscription.Status.ACTIVE,
            end_date=expiry_date
        ).select_related('member', 'member__user')
        
        for subscription in subscriptions:
            try:
                user = subscription.member.user
                if user.email:
                    send_mail(
                        subject=f'Subscription Expiry Notice - {subscription.plan.name}',
                        message=f"""
                        Dear {user.get_full_name()},
                        
                        Your subscription "{subscription.plan.name}" will expire on 
                        {subscription.end_date}. Please renew to continue using our services.
                        
                        Best regards,
                        {subscription.member.gym.name}
                        """,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[user.email],
                        fail_silently=True,
                    )
                    logger.info(f"Sent expiry notification to {user.email}")
            except Exception as e:
                logger.error(f"Failed to send email to {user.email}: {e}")
    
    return len(subscriptions)


@shared_task
def cleanup_old_attendance_records():
    """Delete old attendance records based on retention policy"""
    gyms = GymSettings.objects.select_related('gym')
    
    for gym_settings in gyms:
        retention_days = gym_settings.retention_days_attendance
        cutoff_date = timezone.now().date() - timedelta(days=retention_days)
        
        # Soft delete old records
        count = Attendance.objects.filter(
            member__gym=gym_settings.gym,
            date__lt=cutoff_date,
            is_deleted=False
        ).update(is_deleted=True)
        
        logger.info(f"Cleaned up {count} attendance records for gym {gym_settings.gym.name}")
    
    return True


@shared_task
def cleanup_old_audit_logs():
    """Delete old audit logs based on retention policy"""
    gyms = GymSettings.objects.select_related('gym')
    
    for gym_settings in gyms:
        retention_days = gym_settings.retention_days_audit_log
        cutoff_date = timezone.now() - timedelta(days=retention_days)
        
        count = AuditLog.objects.filter(
            gym=gym_settings.gym,
            created_at__lt=cutoff_date,
            is_deleted=False
        ).update(is_deleted=True)
        
        logger.info(f"Cleaned up {count} audit logs for gym {gym_settings.gym.name}")
    
    return True


@shared_task
def generate_daily_reports():
    """Generate daily reports for all gyms"""
    from .models import Gym
    
    gyms = Gym.objects.filter(is_active=True)
    
    for gym in gyms:
        try:
            stats = DashboardService.get_dashboard_stats(gym)
            
            # You can save stats to a report model or send email
            logger.info(f"Daily report generated for gym {gym.name}: {stats}")
            
        except Exception as e:
            logger.error(f"Failed to generate report for gym {gym.name}: {e}")
    
    return len(gyms)