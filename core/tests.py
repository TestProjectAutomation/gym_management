# core/tests.py
from django.test import TestCase
from django.contrib.auth import get_user_model
from django.utils import timezone
from datetime import timedelta
from .models import Gym, Branch, MemberProfile, SubscriptionPlan, Subscription
from .services import SubscriptionService, AttendanceService

User = get_user_model()


class GymModelTest(TestCase):
    """Test Gym model"""
    
    def setUp(self):
        self.gym = Gym.objects.create(
            name='Test Gym',
            contact_email='test@test.com',
            contact_phone='01123456789',
            address='Test Address'
        )
    
    def test_gym_creation(self):
        self.assertEqual(self.gym.name, 'Test Gym')
        self.assertTrue(self.gym.slug)
        self.assertTrue(self.gym.is_active)
    
    def test_gym_str(self):
        self.assertEqual(str(self.gym), 'Test Gym')


class SubscriptionServiceTest(TestCase):
    """Test subscription service"""
    
    def setUp(self):
        self.gym = Gym.objects.create(
            name='Test Gym',
            contact_email='test@test.com',
            contact_phone='01123456789',
            address='Test Address'
        )
        
        self.branch = Branch.objects.create(
            gym=self.gym,
            name='Main Branch',
            address='Test Address',
            phone='01123456789'
        )
        
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123',
            gym=self.gym,
            branch=self.branch
        )
        
        self.member = MemberProfile.objects.create(
            user=self.user,
            gym=self.gym,
            branch=self.branch,
            phone='01123456789'
        )
        
        self.plan = SubscriptionPlan.objects.create(
            gym=self.gym,
            name='Basic Plan',
            duration_days=30,
            price=100.00,
            is_active=True
        )
    
    def test_create_subscription(self):
        subscription = SubscriptionService.create_subscription(
            member=self.member,
            plan=self.plan
        )
        
        self.assertEqual(subscription.member, self.member)
        self.assertEqual(subscription.plan, self.plan)
        self.assertEqual(subscription.status, Subscription.Status.ACTIVE)
        self.assertEqual(
            subscription.end_date,
            subscription.start_date + timedelta(days=self.plan.duration_days)
        )
    
    def test_no_overlapping_subscriptions(self):
        # Create first subscription
        SubscriptionService.create_subscription(
            member=self.member,
            plan=self.plan,
            start_date=timezone.now().date()
        )
        
        # Try to create overlapping subscription
        with self.assertRaises(Exception):
            SubscriptionService.create_subscription(
                member=self.member,
                plan=self.plan,
                start_date=timezone.now().date()
            )


class AttendanceServiceTest(TestCase):
    """Test attendance service"""
    
    def setUp(self):
        self.gym = Gym.objects.create(
            name='Test Gym',
            contact_email='test@test.com',
            contact_phone='01123456789',
            address='Test Address'
        )
        
        self.branch = Branch.objects.create(
            gym=self.gym,
            name='Main Branch',
            address='Test Address',
            phone='01123456789'
        )
        
        self.user = User.objects.create_user(
            username='testuser',
            email='test@test.com',
            password='testpass123',
            gym=self.gym,
            branch=self.branch
        )
        
        self.member = MemberProfile.objects.create(
            user=self.user,
            gym=self.gym,
            branch=self.branch,
            phone='01123456789'
        )
        
        self.plan = SubscriptionPlan.objects.create(
            gym=self.gym,
            name='Basic Plan',
            duration_days=30,
            price=100.00,
            max_checkins_per_day=2,
            is_active=True
        )
        
        self.subscription = Subscription.objects.create(
            member=self.member,
            plan=self.plan,
            start_date=timezone.now().date(),
            end_date=timezone.now().date() + timedelta(days=30),
            status=Subscription.Status.ACTIVE
        )
    
    def test_check_in_with_active_subscription(self):
        attendance = AttendanceService.check_in(
            member=self.member,
            branch=self.branch,
            check_in_method='qr'
        )
        
        self.assertIsNotNone(attendance)
        self.assertEqual(attendance.member, self.member)
        self.assertIsNone(attendance.check_out_time)
    
    def test_check_in_without_subscription(self):
        # Cancel subscription
        self.subscription.status = Subscription.Status.EXPIRED
        self.subscription.save()
        
        with self.assertRaises(Exception):
            AttendanceService.check_in(
                member=self.member,
                branch=self.branch,
                check_in_method='qr'
            )
    
    def test_check_in_daily_limit(self):
        # First check-in
        AttendanceService.check_in(
            member=self.member,
            branch=self.branch,
            check_in_method='qr'
        )
        
        # Second check-in
        AttendanceService.check_in(
            member=self.member,
            branch=self.branch,
            check_in_method='qr'
        )
        
        # Third check-in should fail
        with self.assertRaises(Exception):
            AttendanceService.check_in(
                member=self.member,
                branch=self.branch,
                check_in_method='qr'
            )
    
    def test_check_out(self):
        attendance = AttendanceService.check_in(
            member=self.member,
            branch=self.branch,
            check_in_method='qr'
        )
        
        checked_out = AttendanceService.check_out(attendance)
        self.assertIsNotNone(checked_out.check_out_time)


class APITest(TestCase):
    """Test API endpoints"""
    
    def setUp(self):
        self.gym = Gym.objects.create(
            name='Test Gym',
            contact_email='test@test.com',
            contact_phone='01123456789',
            address='Test Address'
        )
        
        self.user = User.objects.create_user(
            username='admin',
            email='admin@test.com',
            password='admin123',
            gym=self.gym,
            is_staff=True
        )
    
    def test_register_member(self):
        response = self.client.post('/api/v1/auth/register/', {
            'username': 'newmember',
            'email': 'member@test.com',
            'password': 'Member123!',
            'first_name': 'John',
            'last_name': 'Doe',
            'role': 'member',
            'gym_id': str(self.gym.id)
        })
        
        self.assertEqual(response.status_code, 201)
        self.assertTrue('access' in response.data)
        self.assertTrue('refresh' in response.data)
    
    def test_login(self):
        # Create user
        User.objects.create_user(
            username='testlogin',
            password='test123',
            gym=self.gym
        )
        
        response = self.client.post('/api/v1/auth/login/', {
            'username': 'testlogin',
            'password': 'test123'
        })
        
        self.assertEqual(response.status_code, 200)
        self.assertTrue('access' in response.data)
    
    def test_unauthorized_access(self):
        # Try to access protected endpoint without token
        response = self.client.get('/api/v1/members/')
        self.assertEqual(response.status_code, 401)