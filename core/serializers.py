# serializers.py
from rest_framework import serializers
from django.utils import timezone
from django.core.exceptions import ValidationError as DjangoValidationError
from django.db import transaction
from decimal import Decimal
import uuid

from .models import (
    Gym, Branch, User, MemberProfile, CoachProfile,
    SubscriptionPlan, Subscription, Attendance, Payment,
    WorkoutSession, AuditLog, GymSettings
)


class GymSerializer(serializers.ModelSerializer):
    class Meta:
        model = Gym
        fields = ['id', 'name', 'slug', 'contact_email', 'contact_phone', 
                  'address', 'tax_id', 'logo', 'is_active', 'tier', 
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at', 'slug']


class BranchSerializer(serializers.ModelSerializer):
    gym_name = serializers.CharField(source='gym.name', read_only=True)
    
    class Meta:
        model = Branch
        fields = ['id', 'gym', 'gym_name', 'name', 'code', 'address', 
                  'phone', 'email', 'latitude', 'longitude', 'is_active',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class GymSettingsSerializer(serializers.ModelSerializer):
    class Meta:
        model = GymSettings
        fields = '__all__'
        read_only_fields = ['id', 'created_at', 'updated_at']


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 
                  'full_name', 'gym', 'branch', 'is_active', 'date_joined',
                  'is_deleted']
        read_only_fields = ['id', 'date_joined', 'is_deleted']
    
    def get_full_name(self, obj):
        return obj.get_full_name()


class MemberProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    user_id = serializers.UUIDField(write_only=True)
    gym_name = serializers.CharField(source='gym.name', read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    age = serializers.SerializerMethodField()
    
    class Meta:
        model = MemberProfile
        fields = ['id', 'user', 'user_id', 'gym', 'gym_name', 'branch', 
                  'branch_name', 'phone', 'profile_image', 'date_of_birth',
                  'gender', 'join_date', 'status', 'qr_token', 'qr_code_image',
                  'emergency_contact_name', 'emergency_contact_phone',
                  'emergency_contact_relation', 'medical_notes', 'allergies',
                  'notes', 'age', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at', 'qr_token', 
                           'qr_code_image', 'age']
    
    def get_age(self, obj):
        if obj.date_of_birth:
            today = timezone.now().date()
            return today.year - obj.date_of_birth.year - (
                (today.month, today.day) < (obj.date_of_birth.month, obj.date_of_birth.day)
            )
        return None


class CoachProfileSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    user_id = serializers.UUIDField(write_only=True)
    gym_name = serializers.CharField(source='gym.name', read_only=True)
    assigned_members_count = serializers.IntegerField(read_only=True)
    
    class Meta:
        model = CoachProfile
        fields = ['id', 'user', 'user_id', 'gym', 'gym_name', 'branch',
                  'specialization', 'bio', 'qualifications', 'years_of_experience',
                  'hire_date', 'is_active', 'salary_type', 'salary_amount',
                  'working_hours', 'assigned_members', 'assigned_members_count',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class SubscriptionPlanSerializer(serializers.ModelSerializer):
    class Meta:
        model = SubscriptionPlan
        fields = ['id', 'gym', 'name', 'description', 'duration_days', 
                  'price', 'currency', 'max_checkins_per_day', 'allows_guest',
                  'includes_coaching', 'is_active', 'is_popular', 
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


class SubscriptionSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source='member.user.get_full_name', read_only=True)
    plan_name = serializers.CharField(source='plan.name', read_only=True)
    plan_price = serializers.DecimalField(source='plan.price', read_only=True, max_digits=10, decimal_places=2)
    days_remaining = serializers.SerializerMethodField()
    
    class Meta:
        model = Subscription
        fields = ['id', 'member', 'member_name', 'plan', 'plan_name', 'plan_price',
                  'branch', 'start_date', 'end_date', 'status', 'auto_renew',
                  'cancelled_at', 'cancellation_reason', 'initial_payment',
                  'days_remaining', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_days_remaining(self, obj):
        if obj.status == Subscription.Status.ACTIVE and obj.end_date:
            remaining = (obj.end_date - timezone.now().date()).days
            return max(0, remaining)
        return 0
    
    def validate(self, data):
        if data.get('start_date') and data.get('plan'):
            plan = data.get('plan')
            end_date = data.get('end_date')
            if not end_date:
                end_date = data['start_date'] + timezone.timedelta(days=plan.duration_days)
                data['end_date'] = end_date
            
            if data['start_date'] >= end_date:
                raise serializers.ValidationError({
                    'start_date': 'Start date must be before end date'
                })
        
        return data


class AttendanceSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source='member.user.get_full_name', read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    scanned_by_name = serializers.CharField(source='scanned_by.get_full_name', read_only=True)
    check_in_time_formatted = serializers.DateTimeField(source='check_in_time', read_only=True)
    check_out_time_formatted = serializers.DateTimeField(source='check_out_time', read_only=True)
    
    class Meta:
        model = Attendance
        fields = ['id', 'member', 'member_name', 'branch', 'branch_name',
                  'date', 'check_in_time', 'check_in_time_formatted', 
                  'check_out_time', 'check_out_time_formatted', 
                  'qr_code_scanned', 'scanned_by', 'scanned_by_name',
                  'check_in_method', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at', 'date']
    
    def validate_check_out_time(self, value):
        if value and 'check_in_time' in self.initial_data:
            check_in = self.initial_data.get('check_in_time')
            if value <= check_in:
                raise serializers.ValidationError(
                    'Check-out time must be after check-in time'
                )
        return value


class PaymentSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source='member.user.get_full_name', read_only=True)
    branch_name = serializers.CharField(source='branch.name', read_only=True)
    created_by_name = serializers.CharField(source='created_by.get_full_name', read_only=True)
    
    class Meta:
        model = Payment
        fields = ['id', 'member', 'member_name', 'subscription', 'branch', 
                  'branch_name', 'amount', 'currency', 'payment_date', 
                  'payment_method', 'status', 'action_type', 'transaction_id',
                  'receipt_number', 'created_by', 'created_by_name', 'notes',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at', 'receipt_number']
    
    def validate_amount(self, value):
        if value <= 0:
            raise serializers.ValidationError('Amount must be greater than zero')
        return value


class WorkoutSessionSerializer(serializers.ModelSerializer):
    member_name = serializers.CharField(source='member.user.get_full_name', read_only=True)
    coach_name = serializers.CharField(source='coach.user.get_full_name', read_only=True)
    duration = serializers.SerializerMethodField()
    
    class Meta:
        model = WorkoutSession
        fields = ['id', 'member', 'member_name', 'coach', 'coach_name', 'branch',
                  'title', 'description', 'scheduled_start', 'scheduled_end',
                  'actual_start', 'actual_end', 'status', 'calories_burned',
                  'duration_minutes', 'metrics_data', 'notes', 'duration',
                  'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def get_duration(self, obj):
        if obj.scheduled_start and obj.scheduled_end:
            delta = obj.scheduled_end - obj.scheduled_start
            return delta.total_seconds() / 60
        return None
    
    def validate(self, data):
        if data.get('scheduled_start') and data.get('scheduled_end'):
            if data['scheduled_start'] >= data['scheduled_end']:
                raise serializers.ValidationError({
                    'scheduled_end': 'End time must be after start time'
                })
        
        if data.get('actual_start') and data.get('actual_end'):
            if data['actual_start'] >= data['actual_end']:
                raise serializers.ValidationError({
                    'actual_end': 'End time must be after start time'
                })
        
        return data


class AuditLogSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    gym_name = serializers.CharField(source='gym.name', read_only=True)
    
    class Meta:
        model = AuditLog
        fields = ['id', 'user', 'user_name', 'gym', 'gym_name', 'action_type',
                  'action', 'model_name', 'object_id', 'object_repr', 'changes',
                  'ip_address', 'user_agent', 'created_at', 'updated_at']
        read_only_fields = '__all__'


# Auth Serializers
class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    role = serializers.ChoiceField(choices=['member', 'coach'], write_only=True)
    gym_id = serializers.UUIDField(write_only=True)
    branch_id = serializers.UUIDField(write_only=True, required=False)
    
    class Meta:
        model = User
        fields = ['username', 'email', 'password', 'first_name', 'last_name',
                  'role', 'gym_id', 'branch_id']
    
    def validate_gym_id(self, value):
        try:
            gym = Gym.objects.get(id=value, is_active=True)
            return gym
        except Gym.DoesNotExist:
            raise serializers.ValidationError('Invalid or inactive gym')
    
    def validate_branch_id(self, value):
        if value:
            try:
                branch = Branch.objects.get(id=value, is_active=True)
                return branch
            except Branch.DoesNotExist:
                raise serializers.ValidationError('Invalid or inactive branch')
        return None
    
    def create(self, validated_data):
        role = validated_data.pop('role')
        gym = validated_data.pop('gym_id')
        branch = validated_data.pop('branch_id', None)
        password = validated_data.pop('password')
        
        user = User.objects.create_user(
            **validated_data,
            password=password,
            gym=gym,
            branch=branch,
            is_active=True
        )
        
        # Create profile based on role
        if role == 'member':
            MemberProfile.objects.create(
                user=user,
                gym=gym,
                branch=branch,
                phone='',
                status=MemberProfile.Status.ACTIVE
            )
        elif role == 'coach':
            CoachProfile.objects.create(
                user=user,
                gym=gym,
                branch=branch,
                specialization='',
                years_of_experience=0
            )
        
        return user


class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)


# Dashboard Statistics Serializers
class DashboardStatsSerializer(serializers.Serializer):
    total_members = serializers.IntegerField()
    active_members = serializers.IntegerField()
    total_coaches = serializers.IntegerField()
    active_coaches = serializers.IntegerField()
    total_subscriptions = serializers.IntegerField()
    active_subscriptions = serializers.IntegerField()
    today_attendance = serializers.IntegerField()
    today_checkins = serializers.IntegerField()
    revenue_today = serializers.DecimalField(max_digits=10, decimal_places=2)
    revenue_month = serializers.DecimalField(max_digits=10, decimal_places=2)


class AttendanceStatsSerializer(serializers.Serializer):
    date = serializers.DateField()
    checkins = serializers.IntegerField()
    unique_members = serializers.IntegerField()


class RevenueStatsSerializer(serializers.Serializer):
    date = serializers.DateField()
    amount = serializers.DecimalField(max_digits=10, decimal_places=2)
    count = serializers.IntegerField()