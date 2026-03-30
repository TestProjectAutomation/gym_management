# backend/core/urls.py
from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    GymViewSet, BranchViewSet, UserViewSet, MemberProfileViewSet,
    CoachProfileViewSet, SubscriptionPlanViewSet, SubscriptionViewSet,
    AttendanceViewSet, PaymentViewSet, WorkoutSessionViewSet,
    DashboardViewSet, AuditLogViewSet, AuthViewSet
)

router = DefaultRouter()
router.register(r'gyms', GymViewSet, basename='gym')
router.register(r'branches', BranchViewSet, basename='branch')
router.register(r'users', UserViewSet, basename='user')
router.register(r'members', MemberProfileViewSet, basename='member')
router.register(r'coaches', CoachProfileViewSet, basename='coach')
router.register(r'subscription-plans', SubscriptionPlanViewSet, basename='subscription-plan')
router.register(r'subscriptions', SubscriptionViewSet, basename='subscription')
router.register(r'attendance', AttendanceViewSet, basename='attendance')
router.register(r'payments', PaymentViewSet, basename='payment')
router.register(r'workouts', WorkoutSessionViewSet, basename='workout')
router.register(r'dashboard', DashboardViewSet, basename='dashboard')
router.register(r'audit-logs', AuditLogViewSet, basename='audit-log')
router.register(r'auth', AuthViewSet, basename='auth')

urlpatterns = [
    path('', include(router.urls)),
]