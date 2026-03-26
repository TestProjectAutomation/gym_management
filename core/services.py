# services.py
from django.db import transaction
from django.utils import timezone
from django.core.exceptions import ValidationError
from decimal import Decimal
from datetime import timedelta
import qrcode
from io import BytesIO
from django.core.files import File
import uuid

from .models import (
    MemberProfile, Subscription, SubscriptionPlan, Payment, 
    Attendance, GymSettings, AuditLog, Branch, User
)


class SubscriptionService:
    """Handle subscription business logic"""
    
    @staticmethod
    def create_subscription(member, plan, start_date=None, branch=None, initial_payment=None):
        """Create a new subscription with validation"""
        
        if not start_date:
            start_date = timezone.now().date()
        
        end_date = start_date + timedelta(days=plan.duration_days)
        
        # Check for overlapping active subscriptions
        active_subscriptions = Subscription.objects.filter(
            member=member,
            status=Subscription.Status.ACTIVE,
            end_date__gte=start_date
        )
        
        if active_subscriptions.exists():
            raise ValidationError(
                f"Member already has an active subscription until "
                f"{active_subscriptions.first().end_date}"
            )
        
        subscription = Subscription.objects.create(
            member=member,
            plan=plan,
            branch=branch,
            start_date=start_date,
            end_date=end_date,
            status=Subscription.Status.ACTIVE,
            initial_payment=initial_payment
        )
        
        # Update member status
        member.status = MemberProfile.Status.ACTIVE
        member.save(update_fields=['status'])
        
        return subscription
    
    @staticmethod
    def renew_subscription(subscription, payment=None):
        """Renew an existing subscription"""
        
        if subscription.status != Subscription.Status.ACTIVE:
            raise ValidationError("Cannot renew inactive subscription")
        
        new_start_date = subscription.end_date
        new_end_date = new_start_date + timedelta(days=subscription.plan.duration_days)
        
        # Create new subscription
        new_subscription = Subscription.objects.create(
            member=subscription.member,
            plan=subscription.plan,
            branch=subscription.branch,
            start_date=new_start_date,
            end_date=new_end_date,
            status=Subscription.Status.ACTIVE,
            auto_renew=subscription.auto_renew
        )
        
        return new_subscription
    
    @staticmethod
    def cancel_subscription(subscription, reason=None):
        """Cancel an active subscription"""
        
        if subscription.status != Subscription.Status.ACTIVE:
            raise ValidationError("Only active subscriptions can be cancelled")
        
        subscription.status = Subscription.Status.CANCELLED
        subscription.cancelled_at = timezone.now()
        subscription.cancellation_reason = reason
        subscription.save(update_fields=['status', 'cancelled_at', 'cancellation_reason'])
        
        return subscription
    
    @staticmethod
    def check_expired_subscriptions():
        """Check and mark expired subscriptions"""
        
        expired_subs = Subscription.objects.filter(
            status=Subscription.Status.ACTIVE,
            end_date__lt=timezone.now().date()
        )
        
        count = expired_subs.update(status=Subscription.Status.EXPIRED)
        
        # Update member status for those without any active subscription
        for sub in expired_subs:
            if not Subscription.objects.filter(
                member=sub.member,
                status=Subscription.Status.ACTIVE
            ).exists():
                sub.member.status = MemberProfile.Status.EXPIRED
                sub.member.save(update_fields=['status'])
        
        return count


class PaymentService:
    """Handle payment processing logic"""
    
    @staticmethod
    def process_payment(member, amount, payment_method, branch=None, 
                        subscription=None, created_by=None):
        """Process a payment and update subscription if needed"""
        
        with transaction.atomic():
            # Create payment record
            payment = Payment.objects.create(
                member=member,
                subscription=subscription,
                branch=branch,
                amount=amount,
                payment_method=payment_method,
                status=Payment.Status.COMPLETED,
                created_by=created_by,
                payment_date=timezone.now()
            )
            
            # If payment is for subscription, activate it
            if subscription and subscription.status == Subscription.Status.PENDING:
                subscription.status = Subscription.Status.ACTIVE
                subscription.save(update_fields=['status'])
            
            return payment
    
    @staticmethod
    def refund_payment(payment, reason=None, refunded_by=None):
        """Process a refund for a payment"""
        
        if payment.status == Payment.Status.REFUNDED:
            raise ValidationError("Payment already refunded")
        
        if payment.status != Payment.Status.COMPLETED:
            raise ValidationError("Only completed payments can be refunded")
        
        # Create refund payment record
        refund = Payment.objects.create(
            member=payment.member,
            subscription=payment.subscription,
            branch=payment.branch,
            amount=-payment.amount,
            payment_method=payment.payment_method,
            status=Payment.Status.COMPLETED,
            action_type=Payment.ActionType.REFUND,
            created_by=refunded_by,
            notes=reason,
            payment_date=timezone.now()
        )
        
        # Update original payment
        payment.status = Payment.Status.REFUNDED
        payment.save(update_fields=['status'])
        
        return refund
    
    @staticmethod
    def get_member_revenue(member, start_date=None, end_date=None):
        """Calculate revenue for a member"""
        
        payments = Payment.objects.filter(
            member=member,
            status=Payment.Status.COMPLETED,
            amount__gt=0
        )
        
        if start_date:
            payments = payments.filter(payment_date__gte=start_date)
        if end_date:
            payments = payments.filter(payment_date__lte=end_date)
        
        total = payments.aggregate(total=models.Sum('amount'))['total']
        return total or Decimal('0')


class AttendanceService:
    """Handle attendance check-in/check-out logic"""
    
    @staticmethod
    def check_in(member, branch, check_in_method, scanned_by=None, qr_code=None):
        """Process member check-in"""
        
        # Check if member has active subscription
        active_subscription = Subscription.objects.filter(
            member=member,
            status=Subscription.Status.ACTIVE,
            end_date__gte=timezone.now().date()
        ).first()
        
        if not active_subscription:
            raise ValidationError("No active subscription found")
        
        # Check daily limit
        today = timezone.now().date()
        today_checkins = Attendance.objects.filter(
            member=member,
            date=today
        ).count()
        
        if today_checkins >= active_subscription.plan.max_checkins_per_day:
            raise ValidationError(
                f"Daily check-in limit reached ({active_subscription.plan.max_checkins_per_day})"
            )
        
        # Check for already checked in
        open_session = Attendance.objects.filter(
            member=member,
            date=today,
            check_out_time__isnull=True
        ).exists()
        
        if open_session:
            raise ValidationError("Already checked in, please check out first")
        
        # Create attendance record
        attendance = Attendance.objects.create(
            member=member,
            branch=branch,
            date=today,
            check_in_time=timezone.now(),
            qr_code_scanned=qr_code or '',
            scanned_by=scanned_by,
            check_in_method=check_in_method
        )
        
        return attendance
    
    @staticmethod
    def check_out(attendance):
        """Process member check-out"""
        
        if attendance.check_out_time:
            raise ValidationError("Already checked out")
        
        attendance.check_out_time = timezone.now()
        attendance.save(update_fields=['check_out_time'])
        
        return attendance
    
    @staticmethod
    def get_member_attendance_stats(member, days=30):
        """Get attendance statistics for a member"""
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        attendances = Attendance.objects.filter(
            member=member,
            date__gte=start_date,
            date__lte=end_date
        )
        
        total_checkins = attendances.count()
        days_checked_in = attendances.values('date').distinct().count()
        
        return {
            'total_checkins': total_checkins,
            'unique_days': days_checked_in,
            'attendance_rate': (days_checked_in / days) * 100 if days > 0 else 0
        }


class QRCodeService:
    """Generate and manage QR codes for members"""
    
    @staticmethod
    def generate_qr_code(member):
        """Generate QR code image for member"""
        
        if not member.qr_token:
            member.qr_token = f"MEM-{member.id.hex[:8].upper()}"
            member.save(update_fields=['qr_token'])
        
        # Generate QR code
        qr = qrcode.QRCode(
            version=1,
            error_correction=qrcode.constants.ERROR_CORRECT_L,
            box_size=10,
            border=4,
        )
        qr.add_data(member.qr_token)
        qr.make(fit=True)
        
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Save to BytesIO
        buffer = BytesIO()
        img.save(buffer, format='PNG')
        
        # Create Django File
        filename = f"qr_{member.id.hex}.png"
        member.qr_code_image.save(filename, File(buffer), save=True)
        
        return member.qr_code_image


class DashboardService:
    """Generate dashboard statistics"""
    
    @staticmethod
    def get_dashboard_stats(gym):
        """Get main dashboard statistics"""
        
        today = timezone.now().date()
        month_start = today.replace(day=1)
        
        # Member stats
        members = MemberProfile.objects.filter(gym=gym)
        total_members = members.count()
        active_members = members.filter(status=MemberProfile.Status.ACTIVE).count()
        
        # Coach stats
        coaches = CoachProfile.objects.filter(gym=gym)
        total_coaches = coaches.count()
        active_coaches = coaches.filter(is_active=True).count()
        
        # Subscription stats
        subscriptions = Subscription.objects.filter(member__gym=gym)
        total_subscriptions = subscriptions.count()
        active_subscriptions = subscriptions.filter(
            status=Subscription.Status.ACTIVE,
            end_date__gte=today
        ).count()
        
        # Attendance today
        today_attendance = Attendance.objects.filter(
            member__gym=gym,
            date=today
        )
        today_checkins = today_attendance.count()
        
        # Revenue today and this month
        revenue_today = Payment.objects.filter(
            member__gym=gym,
            status=Payment.Status.COMPLETED,
            payment_date__date=today,
            amount__gt=0
        ).aggregate(total=models.Sum('amount'))['total'] or 0
        
        revenue_month = Payment.objects.filter(
            member__gym=gym,
            status=Payment.Status.COMPLETED,
            payment_date__date__gte=month_start,
            amount__gt=0
        ).aggregate(total=models.Sum('amount'))['total'] or 0
        
        return {
            'total_members': total_members,
            'active_members': active_members,
            'total_coaches': total_coaches,
            'active_coaches': active_coaches,
            'total_subscriptions': total_subscriptions,
            'active_subscriptions': active_subscriptions,
            'today_attendance': today_attendance.count(),
            'today_checkins': today_checkins,
            'revenue_today': revenue_today,
            'revenue_month': revenue_month,
        }
    
    @staticmethod
    def get_attendance_stats(gym, days=30):
        """Get attendance statistics over time"""
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        attendance_stats = []
        current_date = start_date
        
        while current_date <= end_date:
            day_attendance = Attendance.objects.filter(
                member__gym=gym,
                date=current_date
            )
            
            attendance_stats.append({
                'date': current_date,
                'checkins': day_attendance.count(),
                'unique_members': day_attendance.values('member').distinct().count()
            })
            
            current_date += timedelta(days=1)
        
        return attendance_stats
    
    @staticmethod
    def get_revenue_stats(gym, days=30):
        """Get revenue statistics over time"""
        
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=days)
        
        revenue_stats = []
        current_date = start_date
        
        while current_date <= end_date:
            day_payments = Payment.objects.filter(
                member__gym=gym,
                status=Payment.Status.COMPLETED,
                payment_date__date=current_date,
                amount__gt=0
            )
            
            revenue_stats.append({
                'date': current_date,
                'amount': day_payments.aggregate(total=models.Sum('amount'))['total'] or 0,
                'count': day_payments.count()
            })
            
            current_date += timedelta(days=1)
        
        return revenue_stats


class AuditService:
    """Handle audit logging"""
    
    @staticmethod
    def log_action(user, gym, action_type, action, model_name, object_id, 
                   object_repr, changes=None, ip_address=None, user_agent=None):
        """Create an audit log entry"""
        
        AuditLog.objects.create(
            user=user,
            gym=gym,
            action_type=action_type,
            action=action,
            model_name=model_name,
            object_id=str(object_id),
            object_repr=object_repr,
            changes=changes or {},
            ip_address=ip_address,
            user_agent=user_agent
        )