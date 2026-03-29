# core/admin.py
from django.contrib import admin
from django.utils.html import format_html
from django.utils.translation import gettext_lazy as _
from django.urls import reverse
from .models import (
    Gym, Branch, User, MemberProfile, CoachProfile,
    SubscriptionPlan, Subscription, Attendance, Payment,
    WorkoutSession, AuditLog, GymSettings
)


@admin.register(Gym)
class GymAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'tier', 'is_active', 'created_at']
    list_filter = ['tier', 'is_active', 'created_at']
    search_fields = ['name', 'contact_email', 'tax_id']
    prepopulated_fields = {'slug': ('name',)}
    readonly_fields = ['id', 'created_at', 'updated_at']
    fieldsets = (
        (_('Basic Information'), {
            'fields': ('name', 'slug', 'contact_email', 'contact_phone', 'address')
        }),
        (_('Business Details'), {
            'fields': ('tax_id', 'logo', 'tier', 'is_active')
        }),
        (_('Metadata'), {
            'fields': ('id', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(id=request.user.gym_id)


@admin.register(Branch)
class BranchAdmin(admin.ModelAdmin):
    list_display = ['name', 'gym', 'code', 'phone', 'is_active']
    list_filter = ['gym', 'is_active']
    search_fields = ['name', 'code', 'address', 'phone']
    readonly_fields = ['id', 'created_at', 'updated_at']
    raw_id_fields = ['gym']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(gym=request.user.gym)


@admin.register(User)
class UserAdmin(admin.ModelAdmin):
    list_display = ['username', 'email', 'gym', 'branch', 'is_active', 'date_joined']
    list_filter = ['gym', 'branch', 'is_active', 'is_staff', 'is_superuser']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    readonly_fields = ['id', 'created_at', 'updated_at', 'date_joined', 'last_login']
    raw_id_fields = ['gym', 'branch']
    
    fieldsets = (
        (_('Personal Info'), {
            'fields': ('username', 'email', 'first_name', 'last_name', 'password')
        }),
        (_('Tenancy'), {
            'fields': ('gym', 'branch')
        }),
        (_('Permissions'), {
            'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')
        }),
        (_('Important Dates'), {
            'fields': ('last_login', 'date_joined', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(gym=request.user.gym)


@admin.register(MemberProfile)
class MemberProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'gym', 'branch', 'phone', 'status', 'join_date', 'qr_code_preview']
    list_filter = ['gym', 'branch', 'status', 'gender', 'join_date']
    search_fields = ['user__username', 'user__email', 'phone', 'qr_token']
    readonly_fields = ['id', 'created_at', 'updated_at', 'qr_token', 'qr_code_preview_large']
    raw_id_fields = ['user', 'gym', 'branch']
    
    def qr_code_preview(self, obj):
        if obj.qr_code_image:
            return format_html('<img src="{}" width="50" height="50" />', obj.qr_code_image.url)
        return "No QR"
    qr_code_preview.short_description = _("QR Code")
    
    def qr_code_preview_large(self, obj):
        if obj.qr_code_image:
            return format_html('<img src="{}" width="150" height="150" />', obj.qr_code_image.url)
        return "No QR"
    qr_code_preview_large.short_description = _("QR Code")
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(gym=request.user.gym)


@admin.register(CoachProfile)
class CoachProfileAdmin(admin.ModelAdmin):
    list_display = ['user', 'gym', 'branch', 'specialization', 'is_active', 'hire_date']
    list_filter = ['gym', 'branch', 'is_active', 'specialization']
    search_fields = ['user__username', 'user__email', 'specialization']
    readonly_fields = ['id', 'created_at', 'updated_at']
    raw_id_fields = ['user', 'gym', 'branch', 'assigned_members']
    filter_horizontal = ['assigned_members']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(gym=request.user.gym)


@admin.register(SubscriptionPlan)
class SubscriptionPlanAdmin(admin.ModelAdmin):
    list_display = ['name', 'gym', 'price', 'currency', 'duration_days', 'is_active', 'is_popular']
    list_filter = ['gym', 'is_active', 'is_popular', 'currency']
    search_fields = ['name', 'description']
    readonly_fields = ['id', 'created_at', 'updated_at']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(gym=request.user.gym)


@admin.register(Subscription)
class SubscriptionAdmin(admin.ModelAdmin):
    list_display = ['member', 'plan', 'start_date', 'end_date', 'status', 'auto_renew']
    list_filter = ['status', 'auto_renew', 'start_date', 'end_date']
    search_fields = ['member__user__username', 'plan__name']
    readonly_fields = ['id', 'created_at', 'updated_at']
    raw_id_fields = ['member', 'plan', 'branch', 'initial_payment']
    date_hierarchy = 'start_date'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(member__gym=request.user.gym)


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ['member', 'branch', 'check_in_time', 'check_out_time', 'check_in_method']
    list_filter = ['branch', 'check_in_method', 'date']
    search_fields = ['member__user__username', 'qr_code_scanned']
    readonly_fields = ['id', 'created_at', 'updated_at']
    raw_id_fields = ['member', 'branch', 'scanned_by']
    date_hierarchy = 'check_in_time'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(member__gym=request.user.gym)


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ['member', 'amount', 'currency', 'payment_method', 'status', 'payment_date', 'receipt_number']
    list_filter = ['payment_method', 'status', 'payment_date', 'action_type']
    search_fields = ['member__user__username', 'receipt_number', 'transaction_id']
    readonly_fields = ['id', 'created_at', 'updated_at', 'receipt_number']
    raw_id_fields = ['member', 'subscription', 'branch', 'created_by']
    date_hierarchy = 'payment_date'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(member__gym=request.user.gym)


@admin.register(WorkoutSession)
class WorkoutSessionAdmin(admin.ModelAdmin):
    list_display = ['title', 'member', 'coach', 'scheduled_start', 'status']
    list_filter = ['status', 'branch', 'scheduled_start']
    search_fields = ['title', 'member__user__username', 'coach__user__username']
    readonly_fields = ['id', 'created_at', 'updated_at']
    raw_id_fields = ['member', 'coach', 'branch']
    date_hierarchy = 'scheduled_start'
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(member__gym=request.user.gym)


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = ['action_type', 'user', 'model_name', 'action', 'created_at']
    list_filter = ['action_type', 'model_name', 'created_at']
    search_fields = ['action', 'object_repr', 'user__username']
    readonly_fields = ['id', 'created_at', 'updated_at']
    raw_id_fields = ['user', 'gym']
    date_hierarchy = 'created_at'
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(gym=request.user.gym)


@admin.register(GymSettings)
class GymSettingsAdmin(admin.ModelAdmin):
    list_display = ['gym', 'allow_qr_checkin', 'allow_ai_coaching', 'allow_mobile_app']
    list_filter = ['gym', 'allow_qr_checkin', 'allow_ai_coaching']
    readonly_fields = ['id', 'created_at', 'updated_at']
    raw_id_fields = ['gym']
    
    def get_queryset(self, request):
        qs = super().get_queryset(request)
        if request.user.is_superuser:
            return qs
        return qs.filter(gym=request.user.gym)