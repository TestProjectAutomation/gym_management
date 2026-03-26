# permissions.py
from rest_framework import permissions
from django.db import models


class IsOwner(permissions.BasePermission):
    """Allow access only to gym owners"""
    
    def has_permission(self, request, view):
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        # Check if user is gym owner
        if hasattr(request.user, 'is_superuser') and request.user.is_superuser:
            return True
        
        # For gym objects
        if isinstance(obj, models.Model) and hasattr(obj, 'gym'):
            return obj.gym == request.user.gym
        elif isinstance(obj, models.Model) and hasattr(obj, 'user'):
            return obj.user == request.user
        
        return False


class IsGymAdmin(permissions.BasePermission):
    """Allow access to gym admins and owners"""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Check if user has admin role (you can implement role system)
        # For now, we'll check if user is staff or superuser
        return request.user.is_staff or request.user.is_superuser
    
    def has_object_permission(self, request, view, obj):
        # Superuser has full access
        if request.user.is_superuser:
            return True
        
        # Check if object belongs to user's gym
        gym_id = None
        if hasattr(obj, 'gym'):
            gym_id = obj.gym_id
        elif hasattr(obj, 'gym_id'):
            gym_id = obj.gym_id
        
        if gym_id and gym_id == request.user.gym_id:
            return True
        
        # Check if user is staff and object is in their gym
        return request.user.is_staff and hasattr(obj, 'gym') and obj.gym == request.user.gym


class IsCoach(permissions.BasePermission):
    """Allow access to coaches for their assigned members"""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Check if user has coach profile
        return hasattr(request.user, 'coach_profile')
    
    def has_object_permission(self, request, view, obj):
        # Superuser and admins have full access
        if request.user.is_superuser or request.user.is_staff:
            return True
        
        # Check if object is assigned to this coach
        if isinstance(obj, MemberProfile):
            return obj.coaches.filter(id=request.user.coach_profile.id).exists()
        
        if isinstance(obj, WorkoutSession):
            return obj.coach and obj.coach.user == request.user
        
        if hasattr(obj, 'member') and hasattr(obj.member, 'coaches'):
            return obj.member.coaches.filter(id=request.user.coach_profile.id).exists()
        
        return False


class IsMember(permissions.BasePermission):
    """Allow access to members for their own data"""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Check if user has member profile
        return hasattr(request.user, 'member_profile')
    
    def has_object_permission(self, request, view, obj):
        # Check if object belongs to this member
        if isinstance(obj, MemberProfile):
            return obj.user == request.user
        
        if isinstance(obj, Subscription):
            return obj.member.user == request.user
        
        if isinstance(obj, Attendance):
            return obj.member.user == request.user
        
        if isinstance(obj, Payment):
            return obj.member.user == request.user
        
        if isinstance(obj, WorkoutSession):
            return obj.member.user == request.user
        
        return False


class IsGymIsolated(permissions.BasePermission):
    """Ensure users can only access data from their own gym"""
    
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            return False
        
        # Superuser bypass
        if request.user.is_superuser:
            return True
        
        # Store gym_id in view for filtering
        if hasattr(request.user, 'gym_id'):
            view.gym_filter = request.user.gym_id
            return True
        
        return False
    
    def has_object_permission(self, request, view, obj):
        # Superuser bypass
        if request.user.is_superuser:
            return True
        
        # Check gym isolation
        gym_id = None
        if hasattr(obj, 'gym'):
            gym_id = obj.gym_id
        elif hasattr(obj, 'gym_id'):
            gym_id = obj.gym_id
        elif hasattr(obj, 'user') and hasattr(obj.user, 'gym_id'):
            gym_id = obj.user.gym_id
        
        return gym_id == request.user.gym_id