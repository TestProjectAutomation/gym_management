# filters.py
from django_filters import rest_framework as filters
from django.db import models
from .models import (
    MemberProfile, Subscription, Attendance, Payment, 
    WorkoutSession, AuditLog, Branch, User
)


class MemberProfileFilter(filters.FilterSet):
    """Filter for member profiles"""
    
    status = filters.ChoiceFilter(choices=MemberProfile.Status.choices)
    gender = filters.CharFilter(lookup_expr='iexact')
    join_date_start = filters.DateFilter(field_name='join_date', lookup_expr='gte')
    join_date_end = filters.DateFilter(field_name='join_date', lookup_expr='lte')
    age_min = filters.NumberFilter(method='filter_age_min')
    age_max = filters.NumberFilter(method='filter_age_max')
    has_active_subscription = filters.BooleanFilter(method='filter_active_subscription')
    search = filters.CharFilter(method='filter_search')
    
    class Meta:
        model = MemberProfile
        fields = {
            'status': ['exact'],
            'gender': ['exact'],
            'branch': ['exact'],
            'join_date': ['gte', 'lte'],
        }
    
    def filter_age_min(self, queryset, name, value):
        if value:
            # Filter by minimum age (approximate)
            date_limit = timezone.now().date() - timedelta(days=value*365)
            return queryset.filter(date_of_birth__lte=date_limit)
        return queryset
    
    def filter_age_max(self, queryset, name, value):
        if value:
            date_limit = timezone.now().date() - timedelta(days=value*365)
            return queryset.filter(date_of_birth__gte=date_limit)
        return queryset
    
    def filter_active_subscription(self, queryset, name, value):
        if value:
            return queryset.filter(
                subscriptions__status=Subscription.Status.ACTIVE,
                subscriptions__end_date__gte=timezone.now().date()
            ).distinct()
        return queryset
    
    def filter_search(self, queryset, name, value):
        return queryset.filter(
            models.Q(user__first_name__icontains=value) |
            models.Q(user__last_name__icontains=value) |
            models.Q(user__username__icontains=value) |
            models.Q(phone__icontains=value) |
            models.Q(user__email__icontains=value)
        )


class SubscriptionFilter(filters.FilterSet):
    """Filter for subscriptions"""
    
    status = filters.ChoiceFilter(choices=Subscription.Status.choices)
    start_date_start = filters.DateFilter(field_name='start_date', lookup_expr='gte')
    start_date_end = filters.DateFilter(field_name='start_date', lookup_expr='lte')
    end_date_start = filters.DateFilter(field_name='end_date', lookup_expr='gte')
    end_date_end = filters.DateFilter(field_name='end_date', lookup_expr='lte')
    is_active = filters.BooleanFilter(method='filter_is_active')
    auto_renew = filters.BooleanFilter()
    member_name = filters.CharFilter(method='filter_member_name')
    
    class Meta:
        model = Subscription
        fields = {
            'status': ['exact'],
            'plan': ['exact'],
            'branch': ['exact'],
            'start_date': ['gte', 'lte'],
            'end_date': ['gte', 'lte'],
            'auto_renew': ['exact'],
        }
    
    def filter_is_active(self, queryset, name, value):
        if value:
            return queryset.filter(
                status=Subscription.Status.ACTIVE,
                end_date__gte=timezone.now().date()
            )
        return queryset.filter(
            models.Q(status__ne=Subscription.Status.ACTIVE) |
            models.Q(end_date__lt=timezone.now().date())
        )
    
    def filter_member_name(self, queryset, name, value):
        return queryset.filter(
            models.Q(member__user__first_name__icontains=value) |
            models.Q(member__user__last_name__icontains=value)
        )


class AttendanceFilter(filters.FilterSet):
    """Filter for attendance records"""
    
    date_start = filters.DateFilter(field_name='date', lookup_expr='gte')
    date_end = filters.DateFilter(field_name='date', lookup_expr='lte')
    check_in_method = filters.ChoiceFilter(choices=Attendance.CheckInMethod.choices)
    has_check_out = filters.BooleanFilter(method='filter_has_check_out')
    member_name = filters.CharFilter(method='filter_member_name')
    
    class Meta:
        model = Attendance
        fields = {
            'member': ['exact'],
            'branch': ['exact'],
            'date': ['gte', 'lte'],
            'check_in_method': ['exact'],
        }
    
    def filter_has_check_out(self, queryset, name, value):
        if value:
            return queryset.filter(check_out_time__isnull=False)
        return queryset.filter(check_out_time__isnull=True)
    
    def filter_member_name(self, queryset, name, value):
        return queryset.filter(
            models.Q(member__user__first_name__icontains=value) |
            models.Q(member__user__last_name__icontains=value)
        )


class PaymentFilter(filters.FilterSet):
    """Filter for payments"""
    
    status = filters.ChoiceFilter(choices=Payment.Status.choices)
    payment_method = filters.ChoiceFilter(choices=Payment.PaymentMethod.choices)
    payment_date_start = filters.DateFilter(field_name='payment_date', lookup_expr='gte')
    payment_date_end = filters.DateFilter(field_name='payment_date', lookup_expr='lte')
    amount_min = filters.NumberFilter(field_name='amount', lookup_expr='gte')
    amount_max = filters.NumberFilter(field_name='amount', lookup_expr='lte')
    member_name = filters.CharFilter(method='filter_member_name')
    
    class Meta:
        model = Payment
        fields = {
            'member': ['exact'],
            'subscription': ['exact'],
            'branch': ['exact'],
            'status': ['exact'],
            'payment_method': ['exact'],
            'payment_date': ['gte', 'lte'],
            'amount': ['gte', 'lte'],
        }
    
    def filter_member_name(self, queryset, name, value):
        return queryset.filter(
            models.Q(member__user__first_name__icontains=value) |
            models.Q(member__user__last_name__icontains=value)
        )


class WorkoutSessionFilter(filters.FilterSet):
    """Filter for workout sessions"""
    
    status = filters.ChoiceFilter(choices=WorkoutSession.Status.choices)
    scheduled_start_start = filters.DateTimeFilter(field_name='scheduled_start', lookup_expr='gte')
    scheduled_start_end = filters.DateTimeFilter(field_name='scheduled_start', lookup_expr='lte')
    is_upcoming = filters.BooleanFilter(method='filter_is_upcoming')
    member_name = filters.CharFilter(method='filter_member_name')
    
    class Meta:
        model = WorkoutSession
        fields = {
            'member': ['exact'],
            'coach': ['exact'],
            'branch': ['exact'],
            'status': ['exact'],
            'scheduled_start': ['gte', 'lte'],
        }
    
    def filter_is_upcoming(self, queryset, name, value):
        if value:
            return queryset.filter(
                scheduled_start__gte=timezone.now(),
                status__in=[
                    WorkoutSession.Status.SCHEDULED,
                    WorkoutSession.Status.IN_PROGRESS
                ]
            )
        return queryset.filter(scheduled_start__lt=timezone.now())
    
    def filter_member_name(self, queryset, name, value):
        return queryset.filter(
            models.Q(member__user__first_name__icontains=value) |
            models.Q(member__user__last_name__icontains=value)
        )