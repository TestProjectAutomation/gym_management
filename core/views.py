# views.py
from rest_framework import viewsets, status, generics
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework.filters import SearchFilter, OrderingFilter
from django.db.models import Prefetch, Q
from django.utils import timezone
from django.shortcuts import get_object_or_404

from .models import (
    Gym, Branch, User, MemberProfile, CoachProfile,
    SubscriptionPlan, Subscription, Attendance, Payment,
    WorkoutSession, AuditLog, GymSettings
)
from .serializers import (
    GymSerializer, BranchSerializer, UserSerializer,
    MemberProfileSerializer, CoachProfileSerializer,
    SubscriptionPlanSerializer, SubscriptionSerializer,
    AttendanceSerializer, PaymentSerializer, WorkoutSessionSerializer,
    AuditLogSerializer, GymSettingsSerializer, RegisterSerializer,
    DashboardStatsSerializer, AttendanceStatsSerializer, RevenueStatsSerializer
)
from .permissions import (
    IsOwner, IsGymAdmin, IsCoach, IsMember, IsGymIsolated
)
from .filters import (
    MemberProfileFilter, SubscriptionFilter, AttendanceFilter,
    PaymentFilter, WorkoutSessionFilter
)
from .services import (
    SubscriptionService, PaymentService, AttendanceService,
    DashboardService, QRCodeService
)


class GymViewSet(viewsets.ModelViewSet):
    """Manage gyms (tenants)"""
    
    queryset = Gym.objects.filter(is_active=True)
    serializer_class = GymSerializer
    permission_classes = [IsAuthenticated, IsOwner]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    search_fields = ['name', 'contact_email', 'tax_id']
    ordering_fields = ['name', 'created_at']
    ordering = ['name']


class BranchViewSet(viewsets.ModelViewSet):
    """Manage branches"""
    
    serializer_class = BranchSerializer
    permission_classes = [IsAuthenticated, IsGymIsolated, IsGymAdmin]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['is_active', 'gym']
    search_fields = ['name', 'code', 'address', 'phone']
    ordering_fields = ['name', 'created_at']
    ordering = ['gym', 'name']
    
    def get_queryset(self):
        if self.request.user.is_superuser:
            return Branch.objects.filter(is_deleted=False)
        return Branch.objects.filter(
            gym=self.request.user.gym,
            is_deleted=False
        )


class UserViewSet(viewsets.ModelViewSet):
    """Manage users"""
    
    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated, IsGymIsolated, IsGymAdmin]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['is_active', 'gym', 'branch']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    ordering_fields = ['date_joined', 'last_login']
    ordering = ['-date_joined']
    
    def get_queryset(self):
        if self.request.user.is_superuser:
            return User.objects.filter(is_deleted=False)
        return User.objects.filter(
            gym=self.request.user.gym,
            is_deleted=False
        )


class MemberProfileViewSet(viewsets.ModelViewSet):
    """Manage member profiles"""
    
    serializer_class = MemberProfileSerializer
    permission_classes = [IsAuthenticated, IsGymIsolated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = MemberProfileFilter
    search_fields = ['user__first_name', 'user__last_name', 'phone', 'user__email']
    ordering_fields = ['join_date', 'status']
    ordering = ['-join_date']
    
    def get_queryset(self):
        base_queryset = MemberProfile.objects.filter(
            gym=self.request.user.gym,
            is_deleted=False
        ).select_related('user', 'gym', 'branch')
        
        if self.request.user.is_staff or self.request.user.is_superuser:
            return base_queryset
        
        # Coaches can only see their assigned members
        if hasattr(self.request.user, 'coach_profile'):
            return base_queryset.filter(
                coaches=self.request.user.coach_profile
            )
        
        # Members can only see their own profile
        if hasattr(self.request.user, 'member_profile'):
            return base_queryset.filter(user=self.request.user)
        
        return base_queryset.none()
    
    @action(detail=True, methods=['post'])
    def generate_qr(self, request, pk=None):
        """Generate QR code for member"""
        member = self.get_object()
        QRCodeService.generate_qr_code(member)
        return Response({
            'qr_token': member.qr_token,
            'qr_code_url': member.qr_code_image.url if member.qr_code_image else None
        })


class CoachProfileViewSet(viewsets.ModelViewSet):
    """Manage coach profiles"""
    
    serializer_class = CoachProfileSerializer
    permission_classes = [IsAuthenticated, IsGymIsolated, IsGymAdmin]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['is_active', 'specialization']
    search_fields = ['user__first_name', 'user__last_name', 'specialization']
    ordering_fields = ['hire_date', 'years_of_experience']
    ordering = ['-hire_date']
    
    def get_queryset(self):
        if self.request.user.is_superuser:
            return CoachProfile.objects.filter(is_deleted=False)
        return CoachProfile.objects.filter(
            gym=self.request.user.gym,
            is_deleted=False
        ).select_related('user', 'gym', 'branch').prefetch_related('assigned_members')
    
    @action(detail=True, methods=['post'])
    def assign_members(self, request, pk=None):
        """Assign members to coach"""
        coach = self.get_object()
        member_ids = request.data.get('member_ids', [])
        
        members = MemberProfile.objects.filter(
            id__in=member_ids,
            gym=coach.gym
        )
        
        coach.assigned_members.set(members)
        return Response({'status': 'members assigned'})


class SubscriptionPlanViewSet(viewsets.ModelViewSet):
    """Manage subscription plans"""
    
    serializer_class = SubscriptionPlanSerializer
    permission_classes = [IsAuthenticated, IsGymIsolated, IsGymAdmin]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['is_active', 'is_popular', 'allows_guest']
    search_fields = ['name', 'description']
    ordering_fields = ['price', 'duration_days']
    ordering = ['price']
    
    def get_queryset(self):
        if self.request.user.is_superuser:
            return SubscriptionPlan.objects.filter(is_deleted=False)
        return SubscriptionPlan.objects.filter(
            gym=self.request.user.gym,
            is_deleted=False
        )


class SubscriptionViewSet(viewsets.ModelViewSet):
    """Manage subscriptions"""
    
    serializer_class = SubscriptionSerializer
    permission_classes = [IsAuthenticated, IsGymIsolated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = SubscriptionFilter
    ordering_fields = ['start_date', 'end_date', 'created_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        base_queryset = Subscription.objects.filter(
            member__gym=self.request.user.gym,
            is_deleted=False
        ).select_related('member', 'member__user', 'plan', 'branch')
        
        if self.request.user.is_staff or self.request.user.is_superuser:
            return base_queryset
        
        if hasattr(self.request.user, 'member_profile'):
            return base_queryset.filter(member=self.request.user.member_profile)
        
        if hasattr(self.request.user, 'coach_profile'):
            return base_queryset.filter(
                member__coaches=self.request.user.coach_profile
            )
        
        return base_queryset.none()
    
    @action(detail=True, methods=['post'])
    def renew(self, request, pk=None):
        """Renew subscription"""
        subscription = self.get_object()
        
        if subscription.status != Subscription.Status.ACTIVE:
            return Response(
                {'error': 'Only active subscriptions can be renewed'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        new_subscription = SubscriptionService.renew_subscription(subscription)
        serializer = self.get_serializer(new_subscription)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Cancel subscription"""
        subscription = self.get_object()
        reason = request.data.get('reason', '')
        
        SubscriptionService.cancel_subscription(subscription, reason)
        return Response({'status': 'subscription cancelled'})


class AttendanceViewSet(viewsets.ModelViewSet):
    """Manage attendance records"""
    
    serializer_class = AttendanceSerializer
    permission_classes = [IsAuthenticated, IsGymIsolated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = AttendanceFilter
    ordering_fields = ['check_in_time', 'check_out_time', 'date']
    ordering = ['-check_in_time']
    
    def get_queryset(self):
        base_queryset = Attendance.objects.filter(
            member__gym=self.request.user.gym,
            is_deleted=False
        ).select_related('member', 'member__user', 'branch', 'scanned_by')
        
        if self.request.user.is_staff or self.request.user.is_superuser:
            return base_queryset
        
        if hasattr(self.request.user, 'member_profile'):
            return base_queryset.filter(member=self.request.user.member_profile)
        
        if hasattr(self.request.user, 'coach_profile'):
            return base_queryset.filter(
                member__coaches=self.request.user.coach_profile
            )
        
        return base_queryset.none()
    
    @action(detail=False, methods=['post'])
    def check_in(self, request):
        """Check in a member"""
        member_id = request.data.get('member_id')
        branch_id = request.data.get('branch_id')
        method = request.data.get('method', Attendance.CheckInMethod.QR_CODE)
        qr_code = request.data.get('qr_code', '')
        
        member = get_object_or_404(MemberProfile, id=member_id, gym=request.user.gym)
        branch = get_object_or_404(Branch, id=branch_id, gym=request.user.gym, is_active=True)
        
        try:
            attendance = AttendanceService.check_in(
                member=member,
                branch=branch,
                check_in_method=method,
                scanned_by=request.user if request.user.is_staff else None,
                qr_code=qr_code
            )
            serializer = self.get_serializer(attendance)
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['post'])
    def check_out(self, request, pk=None):
        """Check out a member"""
        attendance = self.get_object()
        
        try:
            attendance = AttendanceService.check_out(attendance)
            serializer = self.get_serializer(attendance)
            return Response(serializer.data)
        except Exception as e:
            return Response({'error': str(e)}, status=status.HTTP_400_BAD_REQUEST)


class PaymentViewSet(viewsets.ModelViewSet):
    """Manage payments"""
    
    serializer_class = PaymentSerializer
    permission_classes = [IsAuthenticated, IsGymIsolated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = PaymentFilter
    ordering_fields = ['payment_date', 'amount']
    ordering = ['-payment_date']
    
    def get_queryset(self):
        base_queryset = Payment.objects.filter(
            member__gym=self.request.user.gym,
            is_deleted=False
        ).select_related('member', 'member__user', 'subscription', 'branch', 'created_by')
        
        if self.request.user.is_staff or self.request.user.is_superuser:
            return base_queryset
        
        if hasattr(self.request.user, 'member_profile'):
            return base_queryset.filter(member=self.request.user.member_profile)
        
        if hasattr(self.request.user, 'coach_profile'):
            return base_queryset.filter(
                member__coaches=self.request.user.coach_profile
            )
        
        return base_queryset.none()
    
    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class WorkoutSessionViewSet(viewsets.ModelViewSet):
    """Manage workout sessions"""
    
    serializer_class = WorkoutSessionSerializer
    permission_classes = [IsAuthenticated, IsGymIsolated]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_class = WorkoutSessionFilter
    ordering_fields = ['scheduled_start', 'scheduled_end']
    ordering = ['scheduled_start']
    
    def get_queryset(self):
        base_queryset = WorkoutSession.objects.filter(
            member__gym=self.request.user.gym,
            is_deleted=False
        ).select_related('member', 'member__user', 'coach', 'coach__user', 'branch')
        
        if self.request.user.is_staff or self.request.user.is_superuser:
            return base_queryset
        
        if hasattr(self.request.user, 'member_profile'):
            return base_queryset.filter(member=self.request.user.member_profile)
        
        if hasattr(self.request.user, 'coach_profile'):
            return base_queryset.filter(coach=self.request.user.coach_profile)
        
        return base_queryset.none()
    
    @action(detail=True, methods=['post'])
    def start_session(self, request, pk=None):
        """Start a workout session"""
        session = self.get_object()
        
        if session.status != WorkoutSession.Status.SCHEDULED:
            return Response(
                {'error': 'Session must be scheduled'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        session.status = WorkoutSession.Status.IN_PROGRESS
        session.actual_start = timezone.now()
        session.save(update_fields=['status', 'actual_start'])
        
        return Response({'status': 'session started'})
    
    @action(detail=True, methods=['post'])
    def end_session(self, request, pk=None):
        """End a workout session"""
        session = self.get_object()
        
        if session.status != WorkoutSession.Status.IN_PROGRESS:
            return Response(
                {'error': 'Session must be in progress'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        session.status = WorkoutSession.Status.COMPLETED
        session.actual_end = timezone.now()
        
        if session.actual_start:
            duration = (session.actual_end - session.actual_start).total_seconds() / 60
            session.duration_minutes = int(duration)
        
        session.save(update_fields=['status', 'actual_end', 'duration_minutes'])
        
        return Response({'status': 'session ended'})


class DashboardViewSet(viewsets.ViewSet):
    """Dashboard statistics endpoints"""
    
    permission_classes = [IsAuthenticated, IsGymIsolated]
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """Get main dashboard statistics"""
        stats = DashboardService.get_dashboard_stats(request.user.gym)
        serializer = DashboardStatsSerializer(stats)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def attendance(self, request):
        """Get attendance statistics"""
        days = int(request.query_params.get('days', 30))
        stats = DashboardService.get_attendance_stats(request.user.gym, days)
        serializer = AttendanceStatsSerializer(stats, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def revenue(self, request):
        """Get revenue statistics"""
        days = int(request.query_params.get('days', 30))
        stats = DashboardService.get_revenue_stats(request.user.gym, days)
        serializer = RevenueStatsSerializer(stats, many=True)
        return Response(serializer.data)


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """View audit logs"""
    
    serializer_class = AuditLogSerializer
    permission_classes = [IsAuthenticated, IsGymIsolated, IsGymAdmin]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ['action_type', 'model_name']
    search_fields = ['action', 'object_repr']
    ordering_fields = ['created_at']
    ordering = ['-created_at']
    
    def get_queryset(self):
        if self.request.user.is_superuser:
            return AuditLog.objects.filter(is_deleted=False)
        return AuditLog.objects.filter(
            gym=self.request.user.gym,
            is_deleted=False
        ).select_related('user', 'gym')


class AuthViewSet(viewsets.ViewSet):
    """Authentication endpoints"""
    
    @action(detail=False, methods=['post'])
    def register(self, request):
        """Register a new user"""
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'user': UserSerializer(user).data,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        }, status=status.HTTP_201_CREATED)
    
    @action(detail=False, methods=['post'])
    def login(self, request):
        """Login user"""
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        from django.contrib.auth import authenticate
        user = authenticate(
            username=serializer.validated_data['username'],
            password=serializer.validated_data['password']
        )
        
        if not user:
            return Response(
                {'error': 'Invalid credentials'},
                status=status.HTTP_401_UNAUTHORIZED
            )
        
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'user': UserSerializer(user).data,
            'refresh': str(refresh),
            'access': str(refresh.access_token),
        })
    
    @action(detail=False, methods=['post'])
    def logout(self, request):
        """Logout user (blacklist refresh token)"""
        try:
            refresh_token = request.data.get('refresh')
            if refresh_token:
                from rest_framework_simplejwt.tokens import RefreshToken
                token = RefreshToken(refresh_token)
                token.blacklist()
        except:
            pass
        
        return Response({'status': 'logged out'})