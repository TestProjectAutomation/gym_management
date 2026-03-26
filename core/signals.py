# signals.py
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from .models import Gym, User, MemberProfile, GymSettings, Payment, AuditLog
from .services import QRCodeService, AuditService


@receiver(post_save, sender=Gym)
def create_gym_settings(sender, instance, created, **kwargs):
    """Create default settings when gym is created"""
    if created:
        GymSettings.objects.create(gym=instance)


@receiver(post_save, sender=User)
def create_member_profile(sender, instance, created, **kwargs):
    """Create profile for member users (handled in registration)"""
    # This is handled in registration service, but kept for completeness
    pass


@receiver(pre_save, sender=MemberProfile)
def generate_member_qr_code(sender, instance, **kwargs):
    """Generate QR code when member profile is created"""
    if not instance.id:
        # New member
        if not instance.qr_token:
            instance.qr_token = f"MEM-{instance.user.id.hex[:8].upper()}"
    else:
        # Existing member - check if QR token changed
        try:
            old_instance = MemberProfile.objects.get(pk=instance.pk)
            if not old_instance.qr_token and instance.qr_token:
                QRCodeService.generate_qr_code(instance)
        except MemberProfile.DoesNotExist:
            pass


@receiver(post_save, sender=Payment)
def log_payment_audit(sender, instance, created, **kwargs):
    """Log payment actions"""
    action_type = AuditLog.ActionType.CREATE if created else AuditLog.ActionType.UPDATE
    
    AuditService.log_action(
        user=instance.created_by,
        gym=instance.member.gym,
        action_type=action_type,
        action=f"Payment {action_type}: {instance.amount}",
        model_name='Payment',
        object_id=instance.id,
        object_repr=str(instance),
        changes=None
    )


@receiver(post_save, sender=Subscription)
def log_subscription_audit(sender, instance, created, **kwargs):
    """Log subscription actions"""
    action_type = AuditLog.ActionType.CREATE if created else AuditLog.ActionType.UPDATE
    
    AuditService.log_action(
        user=None,  # Track user from context if available
        gym=instance.member.gym,
        action_type=action_type,
        action=f"Subscription {action_type}: {instance.plan.name}",
        model_name='Subscription',
        object_id=instance.id,
        object_repr=str(instance),
        changes=None
    )