# models.py

import uuid
from django.db import models
from django.contrib.auth.models import AbstractUser
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.utils.text import slugify
from django.db.models import Q

# -------------------------------------------------------------------
# 1. CUSTOM MANAGER FOR SOFT DELETE (IMPROVED)
# -------------------------------------------------------------------

class SoftDeleteManager(models.Manager):
    """
    Custom manager that returns only non-deleted objects by default.
    """
    def get_queryset(self):
        return super().get_queryset().filter(is_deleted=False)


class AllObjectsManager(models.Manager):
    """
    Manager that returns all objects including soft-deleted ones.
    """
    def get_queryset(self):
        return super().get_queryset()


# -------------------------------------------------------------------
# 2. ABSTRACT BASE MODEL WITH SOFT DELETE (IMPROVED)
# -------------------------------------------------------------------

class BaseModel(models.Model):
    """
    Abstract base model with UUID primary key, timestamps, and soft delete.
    Uses custom managers for clean separation of deleted/non-deleted records.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)
    is_deleted = models.BooleanField(_("deleted"), default=False, db_index=True)
    
    # Default manager returns non-deleted objects only
    objects = SoftDeleteManager()
    # Manager that returns all objects including deleted ones
    all_objects = AllObjectsManager()
    
    class Meta:
        abstract = True
        default_manager_name = 'objects'  # Ensures consistency across all models
    
    def delete(self, using=None, keep_parents=False):
        """
        Soft delete: mark as deleted instead of removing from database.
        Preserves data integrity and allows recovery.
        """
        self.is_deleted = True
        self.save(update_fields=['is_deleted', 'updated_at'])
    
    def hard_delete(self):
        """
        Permanently remove from database. Use with caution.
        """
        super().delete()


# -------------------------------------------------------------------
# 3. GYM SETTINGS (FEATURE FLAGS FOR SAAS)
# -------------------------------------------------------------------

class GymSettings(BaseModel):
    """
    Feature flags and configuration per gym. Essential for SaaS customization.
    """
    gym = models.OneToOneField('Gym', on_delete=models.CASCADE, 
                               related_name='settings',
                               verbose_name=_("gym"))
    
    # Feature flags
    allow_qr_checkin = models.BooleanField(_("allow QR check-in"), default=True)
    allow_ai_coaching = models.BooleanField(_("allow AI coaching"), default=False)
    allow_mobile_app = models.BooleanField(_("allow mobile app"), default=True)
    allow_online_payments = models.BooleanField(_("allow online payments"), default=True)
    allow_guest_checkins = models.BooleanField(_("allow guest check-ins"), default=False)
    
    # Business settings
    currency = models.CharField(_("currency"), max_length=10, default='EGP')
    date_format = models.CharField(_("date format"), max_length=20, default='Y-m-d')
    timezone = models.CharField(_("timezone"), max_length=50, default='Africa/Cairo')
    
    # Notification settings
    email_notifications = models.BooleanField(_("email notifications"), default=True)
    sms_notifications = models.BooleanField(_("SMS notifications"), default=False)
    
    # Retention policies
    retention_days_attendance = models.PositiveIntegerField(_("attendance retention days"), default=365)
    retention_days_audit_log = models.PositiveIntegerField(_("audit log retention days"), default=730)
    
    class Meta:
        verbose_name = _("gym settings")
        verbose_name_plural = _("gym settings")
    
    def __str__(self):
        return f"Settings for {self.gym.name}"


# -------------------------------------------------------------------
# 4. MULTI-TENANCY CORE MODELS
# -------------------------------------------------------------------

class Gym(BaseModel):
    """
    Represents a tenant (gym company). This is the root isolation boundary.
    All data in the system MUST be scoped to a Gym for strict multi-tenancy.
    """
    name = models.CharField(_("gym name"), max_length=255, db_index=True)
    slug = models.SlugField(_("slug"), unique=True, db_index=True, 
                           help_text=_("Used for subdomain routing and API endpoints"))
    contact_email = models.EmailField(_("contact email"))
    contact_phone = models.CharField(_("contact phone"), max_length=20)
    address = models.TextField(_("address"))
    tax_id = models.CharField(_("tax ID"), max_length=50, blank=True, 
                              help_text=_("Tax identification number for invoices"))
    logo = models.ImageField(_("logo"), upload_to='gym_logos/', blank=True, null=True)
    is_active = models.BooleanField(_("active"), default=True, db_index=True)
    
    # Subscription tier for the gym itself (SaaS billing)
    class Tier(models.TextChoices):
        BASIC = 'basic', _('Basic')
        PROFESSIONAL = 'professional', _('Professional')
        ENTERPRISE = 'enterprise', _('Enterprise')
    
    tier = models.CharField(_("subscription tier"), max_length=20, 
                           choices=Tier.choices, default=Tier.BASIC)
    
    class Meta:
        verbose_name = _("gym")
        verbose_name_plural = _("gyms")
        ordering = ['name']
        indexes = [
            models.Index(fields=['slug', 'is_active']),
            models.Index(fields=['created_at']),  # For analytics queries
        ]
    
    def __str__(self):
        return self.name
    
    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)
    
    def create_default_settings(self):
        """Create default settings when gym is created."""
        GymSettings.objects.get_or_create(gym=self)


class Branch(BaseModel):
    """
    Physical location belonging to a Gym. All operational data is linked to a branch.
    """
    gym = models.ForeignKey(Gym, on_delete=models.CASCADE, 
                           related_name='branches', 
                           verbose_name=_("gym"),
                           db_index=True)
    name = models.CharField(_("branch name"), max_length=255)
    code = models.CharField(_("branch code"), max_length=20, blank=True,
                           help_text=_("Short code for quick identification"))
    address = models.TextField(_("address"))
    phone = models.CharField(_("phone number"), max_length=20)
    email = models.EmailField(_("email address"), blank=True)
    latitude = models.DecimalField(_("latitude"), max_digits=9, decimal_places=6, 
                                   null=True, blank=True)
    longitude = models.DecimalField(_("longitude"), max_digits=9, decimal_places=6, 
                                    null=True, blank=True)
    is_active = models.BooleanField(_("active"), default=True, db_index=True)
    
    class Meta:
        verbose_name = _("branch")
        verbose_name_plural = _("branches")
        ordering = ['gym', 'name']
        unique_together = [['gym', 'name']]  # Prevent duplicate branch names within a gym
        indexes = [
            models.Index(fields=['gym', 'is_active']),
            models.Index(fields=['code']),
            models.Index(fields=['gym', 'created_at']),  # Performance boost
        ]
    
    def __str__(self):
        return f"{self.gym.name} - {self.name}"


# -------------------------------------------------------------------
# 5. CUSTOM USER MODEL (IMPROVED)
# -------------------------------------------------------------------

class User(AbstractUser):
    """
    Custom User model with multi-tenancy support.
    IMPORTANT: Does NOT inherit from BaseModel to avoid conflicts.
    UUID is used as primary key for security and scalability.
    """
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    gym = models.ForeignKey(Gym, on_delete=models.CASCADE, 
                           related_name='users',
                           verbose_name=_("gym"),
                           db_index=True)
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, 
                               null=True, blank=True,
                               related_name='users',
                               verbose_name=_("branch"),
                               db_index=True)
    
    # Override groups and permissions to avoid reverse accessor clashes
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name=_('groups'),
        blank=True,
        help_text=_('The groups this user belongs to.'),
        related_name="gym_user_groups",
        related_query_name="gym_user",
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name=_('user permissions'),
        blank=True,
        help_text=_('Specific permissions for this user.'),
        related_name="gym_user_permissions",
        related_query_name="gym_user",
    )
    
    # Soft delete fields (manual implementation to avoid BaseModel conflict)
    created_at = models.DateTimeField(_("created at"), auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(_("updated at"), auto_now=True)
    is_deleted = models.BooleanField(_("deleted"), default=False, db_index=True)
    
    # Custom managers for soft delete
    objects = SoftDeleteManager()
    all_objects = AllObjectsManager()
    
    class Meta:
        verbose_name = _("user")
        verbose_name_plural = _("users")
        ordering = ['-date_joined']
        indexes = [
            models.Index(fields=['gym', 'is_active']),
            models.Index(fields=['email', 'gym']),
            models.Index(fields=['gym', 'created_at']),  # Analytics
        ]
    
    def __str__(self):
        return self.get_full_name() or self.username
    
    def delete(self, using=None, keep_parents=False):
        """Soft delete for user."""
        self.is_deleted = True
        self.save(update_fields=['is_deleted', 'updated_at'])
    
    def hard_delete(self):
        """Permanently delete user."""
        super().delete()


# -------------------------------------------------------------------
# 6. MEMBER PROFILE (IMPROVED)
# -------------------------------------------------------------------

class MemberProfile(BaseModel):
    """
    Extended profile for gym members. Scoped to Gym for fast filtering.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, 
                                related_name='member_profile',
                                verbose_name=_("user"))
    gym = models.ForeignKey(Gym, on_delete=models.CASCADE,
                           related_name='member_profiles',
                           verbose_name=_("gym"),
                           db_index=True)
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL,
                               null=True, blank=True,
                               related_name='member_profiles',
                               verbose_name=_("primary branch"))
    
    # Personal information
    phone = models.CharField(_("phone number"), max_length=20, db_index=True)
    profile_image = models.ImageField(_("profile image"), upload_to='members/', 
                                      blank=True, null=True)
    date_of_birth = models.DateField(_("date of birth"), null=True, blank=True)
    gender = models.CharField(_("gender"), max_length=10, blank=True)
    
    # Membership information
    join_date = models.DateField(_("join date"), default=timezone.now, db_index=True)
    
    class Status(models.TextChoices):
        ACTIVE = 'active', _('Active')
        EXPIRED = 'expired', _('Expired')
        SUSPENDED = 'suspended', _('Suspended')
        CANCELLED = 'cancelled', _('Cancelled')
    
    status = models.CharField(_("status"), max_length=20, 
                             choices=Status.choices, 
                             default=Status.ACTIVE, 
                             db_index=True)
    
    # QR Code for check-in (enhanced with both token and image)
    qr_token = models.CharField(_("QR token"), max_length=255, unique=True, 
                               blank=True, null=True, db_index=True,
                               help_text=_("Unique token for QR code generation"))
    qr_code_image = models.ImageField(_("QR code image"), upload_to='qr_codes/', 
                                     blank=True, null=True,
                                     help_text=_("Generated QR code image"))
    
    # Emergency contact
    emergency_contact_name = models.CharField(_("emergency contact name"), 
                                             max_length=255, blank=True)
    emergency_contact_phone = models.CharField(_("emergency contact phone"), 
                                              max_length=20, blank=True)
    emergency_contact_relation = models.CharField(_("relation"), max_length=50, blank=True)
    
    # Medical information
    medical_notes = models.TextField(_("medical notes"), blank=True)
    allergies = models.TextField(_("allergies"), blank=True)
    
    # Additional fields
    notes = models.TextField(_("notes"), blank=True)
    
    class Meta:
        verbose_name = _("member profile")
        verbose_name_plural = _("member profiles")
        ordering = ['-join_date']
        indexes = [
            models.Index(fields=['gym', 'status']),
            models.Index(fields=['user', 'gym']),
            models.Index(fields=['phone', 'gym']),
            models.Index(fields=['qr_token']),
            models.Index(fields=['gym', 'join_date']),  # Analytics
        ]
    
    def __str__(self):
        return f"Member: {self.user.get_full_name()} - {self.gym.name}"
    
    def save(self, *args, **kwargs):
        # Auto-generate QR token if not provided
        if not self.qr_token:
            self.qr_token = f"MEM-{self.id.hex[:8].upper()}" if self.id else f"MEM-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)


# -------------------------------------------------------------------
# 7. COACH PROFILE
# -------------------------------------------------------------------

class CoachProfile(BaseModel):
    """
    Extended profile for coaches/instructors.
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, 
                                related_name='coach_profile',
                                verbose_name=_("user"))
    gym = models.ForeignKey(Gym, on_delete=models.CASCADE,
                           related_name='coach_profiles',
                           verbose_name=_("gym"),
                           db_index=True)
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL,
                               null=True, blank=True,
                               related_name='coach_profiles',
                               verbose_name=_("primary branch"))
    
    # Professional information
    specialization = models.CharField(_("specialization"), max_length=255,
                                     help_text=_("e.g., Yoga, Powerlifting, Nutrition"))
    bio = models.TextField(_("biography"), blank=True)
    qualifications = models.TextField(_("qualifications"), blank=True)
    years_of_experience = models.PositiveIntegerField(_("years of experience"), default=0)
    hire_date = models.DateField(_("hire date"), default=timezone.now)
    
    # Employment
    is_active = models.BooleanField(_("active"), default=True, db_index=True)
    salary_type = models.CharField(_("salary type"), max_length=20, blank=True)
    salary_amount = models.DecimalField(_("salary amount"), max_digits=10, 
                                        decimal_places=2, null=True, blank=True)
    
    # Schedule
    working_hours = models.JSONField(_("working hours"), default=dict, blank=True,
                                    help_text=_("JSON field for weekly schedule"))
    
    # Relationships
    assigned_members = models.ManyToManyField(MemberProfile, 
                                              related_name='coaches', 
                                              blank=True,
                                              verbose_name=_("assigned members"))
    
    class Meta:
        verbose_name = _("coach profile")
        verbose_name_plural = _("coach profiles")
        ordering = ['-hire_date']
        indexes = [
            models.Index(fields=['gym', 'is_active']),
            models.Index(fields=['specialization']),
            models.Index(fields=['gym', 'hire_date']),
        ]
    
    def __str__(self):
        return f"Coach: {self.user.get_full_name()} - {self.specialization}"


# -------------------------------------------------------------------
# 8. SUBSCRIPTION SYSTEM (IMPROVED OVERLAP VALIDATION)
# -------------------------------------------------------------------

class SubscriptionPlan(BaseModel):
    """
    Subscription plans offered by a gym. Scoped to Gym for multi-tenancy.
    """
    gym = models.ForeignKey(Gym, on_delete=models.CASCADE, 
                           related_name='subscription_plans',
                           verbose_name=_("gym"),
                           db_index=True)
    name = models.CharField(_("plan name"), max_length=255)
    description = models.TextField(_("description"), blank=True)
    
    duration_days = models.PositiveIntegerField(_("duration (days)"),
                                               help_text=_("Number of days the subscription is valid"))
    price = models.DecimalField(_("price"), max_digits=10, decimal_places=2)
    
    # Currency support
    currency = models.CharField(_("currency"), max_length=10, default='EGP')
    
    # Features
    max_checkins_per_day = models.PositiveIntegerField(_("max check-ins per day"), default=1)
    allows_guest = models.BooleanField(_("allows guest"), default=False)
    includes_coaching = models.BooleanField(_("includes coaching"), default=False)
    
    is_active = models.BooleanField(_("active"), default=True, db_index=True)
    is_popular = models.BooleanField(_("popular"), default=False)
    
    class Meta:
        verbose_name = _("subscription plan")
        verbose_name_plural = _("subscription plans")
        ordering = ['gym', 'price']
        unique_together = [['gym', 'name']]  # Unique plan names per gym
        indexes = [
            models.Index(fields=['gym', 'is_active']),
            models.Index(fields=['gym', 'price']),
        ]
    
    def __str__(self):
        return f"{self.name} - {self.price} {self.currency} ({self.gym.name})"


class Subscription(BaseModel):
    """
    Member's subscription record. Enforces business rules like no overlapping active subscriptions.
    """
    member = models.ForeignKey(MemberProfile, on_delete=models.CASCADE, 
                               related_name='subscriptions',
                               verbose_name=_("member"),
                               db_index=True)
    plan = models.ForeignKey(SubscriptionPlan, on_delete=models.PROTECT, 
                            related_name='subscriptions',
                            verbose_name=_("plan"))
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, 
                               null=True, blank=True,
                               related_name='subscriptions',
                               verbose_name=_("purchasing branch"))
    
    start_date = models.DateField(_("start date"), db_index=True)
    end_date = models.DateField(_("end date"), db_index=True)
    
    class Status(models.TextChoices):
        ACTIVE = 'active', _('Active')
        EXPIRED = 'expired', _('Expired')
        CANCELLED = 'cancelled', _('Cancelled')
        PENDING = 'pending', _('Pending')
    
    status = models.CharField(_("status"), max_length=20, 
                             choices=Status.choices, 
                             default=Status.PENDING, 
                             db_index=True)
    auto_renew = models.BooleanField(_("auto-renew"), default=False)
    
    # Tracking
    cancelled_at = models.DateTimeField(_("cancelled at"), null=True, blank=True)
    cancellation_reason = models.TextField(_("cancellation reason"), blank=True)
    
    # Payment reference
    initial_payment = models.OneToOneField('Payment', on_delete=models.SET_NULL, 
                                          null=True, blank=True,
                                          related_name='initialized_subscription',
                                          verbose_name=_("initial payment"))
    
    class Meta:
        verbose_name = _("subscription")
        verbose_name_plural = _("subscriptions")
        ordering = ['-start_date']
        indexes = [
            models.Index(fields=['member', 'status']),
            models.Index(fields=['end_date']),  # For expiry queries
            models.Index(fields=['start_date', 'end_date']),
            models.Index(fields=['member', 'start_date', 'end_date']),  # For overlap checks
        ]
        constraints = [
            # Ensure end_date is after start_date
            models.CheckConstraint(
                check=models.Q(end_date__gt=models.F('start_date')),
                name='subscription_end_date_after_start_date'
            ),
        ]
    
    def __str__(self):
        return f"{self.member.user.get_full_name()} - {self.plan.name} ({self.status})"
    
    def save(self, *args, **kwargs):
        # Auto-calculate end_date if not provided
        if not self.end_date and self.start_date and self.plan:
            self.end_date = self.start_date + timezone.timedelta(days=self.plan.duration_days)
        
        # Validate no overlapping active subscriptions (improved logic)
        if self.status == self.Status.ACTIVE:
            overlapping = Subscription.objects.filter(
                member=self.member,
                status=self.Status.ACTIVE,
                start_date__lte=self.end_date,  # Existing subscription starts before or at this one's end
                end_date__gte=self.start_date    # Existing subscription ends after or at this one's start
            ).exclude(pk=self.pk)
            
            if overlapping.exists():
                raise ValidationError(
                    _("Member already has an active subscription during this period. "
                      "Overlapping period: %(start)s to %(end)s") % {
                        'start': overlapping.first().start_date,
                        'end': overlapping.first().end_date
                    }
                )
        
        super().save(*args, **kwargs)


# -------------------------------------------------------------------
# 9. ATTENDANCE SYSTEM (OPTIMIZED WITH PARTITIONING READY)
# -------------------------------------------------------------------

class Attendance(BaseModel):
    """
    Tracks member check-ins and check-outs. Optimized for high-volume logging.
    """
    member = models.ForeignKey(MemberProfile, on_delete=models.CASCADE, 
                              related_name='attendances',
                              verbose_name=_("member"),
                              db_index=True)
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, 
                              related_name='attendances',
                              verbose_name=_("branch"),
                              db_index=True)
    
    # Separate date field for fast daily filtering
    date = models.DateField(_("date"), db_index=True)
    check_in_time = models.DateTimeField(_("check-in time"), db_index=True)
    check_out_time = models.DateTimeField(_("check-out time"), null=True, blank=True)
    
    # QR Code scan data
    qr_code_scanned = models.CharField(_("QR code scanned"), max_length=255, blank=True)
    scanned_by = models.ForeignKey(User, on_delete=models.SET_NULL, 
                                   null=True, blank=True,
                                   related_name='scanned_attendances',
                                   verbose_name=_("scanned by"))
    
    # Check-in method
    class CheckInMethod(models.TextChoices):
        QR_CODE = 'qr', _('QR Code')
        MANUAL = 'manual', _('Manual')
        NFC = 'nfc', _('NFC')
        FACE = 'face', _('Face Recognition')
    
    check_in_method = models.CharField(_("check-in method"), max_length=10,
                                      choices=CheckInMethod.choices,
                                      default=CheckInMethod.QR_CODE)
    
    class Meta:
        verbose_name = _("attendance")
        verbose_name_plural = _("attendances")
        ordering = ['-check_in_time']
        indexes = [
            models.Index(fields=['member', 'date']),
            models.Index(fields=['branch', 'date']),
            models.Index(fields=['date', 'check_in_time']),
            models.Index(fields=['qr_code_scanned']),
            models.Index(fields=['member', 'check_in_time']),  # For quick lookups
        ]
        # Note: For very large scale, consider database partitioning by date
        unique_together = [['member', 'date', 'check_in_time']]  # Prevent duplicate check-ins
    
    def __str__(self):
        return f"{self.member.user.get_full_name()} - {self.check_in_time}"
    
    def save(self, *args, **kwargs):
        # Auto-set date from check_in_time
        if self.check_in_time and not self.date:
            self.date = self.check_in_time.date()
        super().save(*args, **kwargs)


# -------------------------------------------------------------------
# 10. PAYMENT SYSTEM (ENHANCED WITH CURRENCY)
# -------------------------------------------------------------------

class Payment(BaseModel):
    """
    Financial transactions tracking. Fully auditable with user tracking.
    """
    member = models.ForeignKey(MemberProfile, on_delete=models.CASCADE, 
                              related_name='payments',
                              verbose_name=_("member"),
                              db_index=True)
    subscription = models.ForeignKey(Subscription, on_delete=models.SET_NULL, 
                                     null=True, blank=True,
                                     related_name='payments',
                                     verbose_name=_("subscription"))
    branch = models.ForeignKey(Branch, on_delete=models.SET_NULL, 
                               null=True, blank=True,
                               related_name='payments',
                               verbose_name=_("branch"))
    
    # Payment details
    amount = models.DecimalField(_("amount"), max_digits=10, decimal_places=2)
    currency = models.CharField(_("currency"), max_length=10, default='EGP')
    payment_date = models.DateTimeField(_("payment date"), default=timezone.now, db_index=True)
    
    class PaymentMethod(models.TextChoices):
        CASH = 'cash', _('Cash')
        CREDIT_CARD = 'credit_card', _('Credit Card')
        DEBIT_CARD = 'debit_card', _('Debit Card')
        BANK_TRANSFER = 'bank_transfer', _('Bank Transfer')
        ONLINE = 'online', _('Online Gateway')
        MOBILE_MONEY = 'mobile_money', _('Mobile Money')
    
    class Status(models.TextChoices):
        PENDING = 'pending', _('Pending')
        COMPLETED = 'completed', _('Completed')
        FAILED = 'failed', _('Failed')
        REFUNDED = 'refunded', _('Refunded')
        PARTIAL = 'partial', _('Partial')
    
    class ActionType(models.TextChoices):
        CREATE = 'create', _('Create')
        UPDATE = 'update', _('Update')
        DELETE = 'delete', _('Delete')
        REFUND = 'refund', _('Refund')
    
    payment_method = models.CharField(_("payment method"), max_length=20, 
                                     choices=PaymentMethod.choices, 
                                     db_index=True)
    status = models.CharField(_("status"), max_length=20, 
                             choices=Status.choices, 
                             default=Status.PENDING, 
                             db_index=True)
    action_type = models.CharField(_("action type"), max_length=10,
                                  choices=ActionType.choices,
                                  default=ActionType.CREATE,
                                  db_index=True)
    
    # Transaction tracking
    transaction_id = models.CharField(_("transaction ID"), max_length=255, 
                                     blank=True, db_index=True,
                                     help_text=_("Gateway transaction ID"))
    receipt_number = models.CharField(_("receipt number"), max_length=50, 
                                     blank=True, unique=True)
    
    # Audit trail
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, 
                                  null=True, blank=True,
                                  related_name='created_payments',
                                  verbose_name=_("created by"))
    
    # Notes
    notes = models.TextField(_("notes"), blank=True)
    
    class Meta:
        verbose_name = _("payment")
        verbose_name_plural = _("payments")
        ordering = ['-payment_date']
        indexes = [
            models.Index(fields=['member', 'payment_date']),
            models.Index(fields=['status', 'payment_date']),
            models.Index(fields=['transaction_id']),
            models.Index(fields=['receipt_number']),
            models.Index(fields=['created_by', 'payment_date']),
            models.Index(fields=['action_type', 'created_at']),  # For audit
        ]
    
    def __str__(self):
        return f"{self.member.user.get_full_name()} - {self.amount} {self.currency} ({self.status})"
    
    def save(self, *args, **kwargs):
        # Auto-generate receipt number if not provided
        if not self.receipt_number:
            self.receipt_number = f"INV-{self.id.hex[:8].upper()}" if self.id else f"INV-{uuid.uuid4().hex[:8].upper()}"
        super().save(*args, **kwargs)


# -------------------------------------------------------------------
# 11. EXTENSIBILITY MODELS (FUTURE FEATURES)
# -------------------------------------------------------------------

class WorkoutSession(BaseModel):
    """
    Scheduled or logged workout sessions. Enables AI coaching and mobile app features.
    """
    member = models.ForeignKey(MemberProfile, on_delete=models.CASCADE, 
                              related_name='workout_sessions',
                              verbose_name=_("member"))
    coach = models.ForeignKey(CoachProfile, on_delete=models.SET_NULL, 
                             null=True, blank=True,
                             related_name='led_sessions',
                             verbose_name=_("coach"))
    branch = models.ForeignKey(Branch, on_delete=models.CASCADE, 
                              related_name='workout_sessions',
                              verbose_name=_("branch"))
    
    title = models.CharField(_("title"), max_length=255)
    description = models.TextField(_("description"), blank=True)
    
    scheduled_start = models.DateTimeField(_("scheduled start time"), db_index=True)
    scheduled_end = models.DateTimeField(_("scheduled end time"))
    actual_start = models.DateTimeField(_("actual start time"), null=True, blank=True)
    actual_end = models.DateTimeField(_("actual end time"), null=True, blank=True)
    
    class Status(models.TextChoices):
        SCHEDULED = 'scheduled', _('Scheduled')
        IN_PROGRESS = 'in_progress', _('In Progress')
        COMPLETED = 'completed', _('Completed')
        CANCELLED = 'cancelled', _('Cancelled')
        NO_SHOW = 'no_show', _('No Show')
    
    status = models.CharField(_("status"), max_length=20, 
                             choices=Status.choices, 
                             default=Status.SCHEDULED,
                             db_index=True)
    
    # Metrics
    calories_burned = models.PositiveIntegerField(_("calories burned"), null=True, blank=True)
    duration_minutes = models.PositiveIntegerField(_("duration (minutes)"), null=True, blank=True)
    
    # Data for AI
    metrics_data = models.JSONField(_("metrics data"), default=dict, blank=True)
    notes = models.TextField(_("notes"), blank=True)
    
    class Meta:
        verbose_name = _("workout session")
        verbose_name_plural = _("workout sessions")
        ordering = ['-scheduled_start']
        indexes = [
            models.Index(fields=['member', 'scheduled_start']),
            models.Index(fields=['coach', 'scheduled_start']),
            models.Index(fields=['status']),
            models.Index(fields=['branch', 'scheduled_start']),
        ]
    
    def __str__(self):
        return f"{self.title} - {self.member.user.get_full_name()}"


# -------------------------------------------------------------------
# 12. AUDIT LOG (ENHANCED WITH ACTION TYPES)
# -------------------------------------------------------------------

class AuditLog(BaseModel):
    """
    Track all important actions for security and compliance.
    """
    class ActionType(models.TextChoices):
        CREATE = 'create', _('Create')
        UPDATE = 'update', _('Update')
        DELETE = 'delete', _('Delete')
        VIEW = 'view', _('View')
        LOGIN = 'login', _('Login')
        LOGOUT = 'logout', _('Logout')
        EXPORT = 'export', _('Export')
        IMPORT = 'import', _('Import')
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, 
                            null=True, blank=True,
                            related_name='audit_logs',
                            verbose_name=_("user"))
    gym = models.ForeignKey(Gym, on_delete=models.CASCADE, 
                           related_name='audit_logs',
                           verbose_name=_("gym"),
                           db_index=True)
    
    action_type = models.CharField(_("action type"), max_length=20,
                                  choices=ActionType.choices,
                                  db_index=True)
    action = models.CharField(_("action description"), max_length=255)
    model_name = models.CharField(_("model name"), max_length=100)
    object_id = models.CharField(_("object ID"), max_length=255)
    object_repr = models.CharField(_("object representation"), max_length=255)
    
    changes = models.JSONField(_("changes"), default=dict, blank=True)
    ip_address = models.GenericIPAddressField(_("IP address"), null=True, blank=True)
    user_agent = models.TextField(_("user agent"), blank=True)
    
    class Meta:
        verbose_name = _("audit log")
        verbose_name_plural = _("audit logs")
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['gym', 'action_type', 'created_at']),
            models.Index(fields=['user', 'created_at']),
            models.Index(fields=['model_name', 'object_id']),
            models.Index(fields=['gym', 'created_at']),  # For analytics
            models.Index(fields=['action_type', 'created_at']),  # For filtering
        ]
    
    def __str__(self):
        return f"{self.action_type} - {self.model_name} - {self.created_at}"