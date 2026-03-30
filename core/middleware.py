# core/middleware.py
import logging
from django.utils.deprecation import MiddlewareMixin
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
import json
from .services import AuditService
from .models import AuditLog
from django.utils import timezone 
from django.conf import settings


logger = logging.getLogger(__name__)


class TenancyMiddleware(MiddlewareMixin):
    """
    Middleware to enforce multi-tenancy isolation
    """
    
    def process_request(self, request):
        """Add gym context to request"""
        if request.user and request.user.is_authenticated:
            # Store gym in request for easy access
            request.current_gym = request.user.gym
        else:
            request.current_gym = None
        
        # Optional: Get gym from subdomain
        # host = request.get_host().split(':')[0]
        # subdomain = host.split('.')[0] if '.' in host else None
        # if subdomain and subdomain != 'www':
        #     try:
        #         gym = Gym.objects.get(slug=subdomain, is_active=True)
        #         request.current_gym = gym
        #     except Gym.DoesNotExist:
        #         pass
        
        return None
    
    def process_response(self, request, response):
        """Add gym info to response headers"""
        if hasattr(request, 'current_gym') and request.current_gym:
            response['X-Gym-ID'] = str(request.current_gym.id)
            response['X-Gym-Name'] = request.current_gym.name
        return response


class AuditMiddleware(MiddlewareMixin):
    """
    Middleware to log all API requests
    """
    
    def __init__(self, get_response):
        super().__init__(get_response)
        self.get_response = get_response
        self.exclude_paths = ['/api/v1/auth/login', '/api/v1/auth/register', '/admin/']
    
    def process_request(self, request):
        """Store request start time"""
        request._start_time = timezone.now()
        return None
    
    def process_response(self, request, response):
        """Log API requests"""
        # Skip logging for certain paths
        if any(path in request.path for path in self.exclude_paths):
            return response
        
        # Skip if not API
        if not request.path.startswith('/api/'):
            return response
        
        # Log if user is authenticated
        if request.user and request.user.is_authenticated:
            try:
                # Calculate duration
                if hasattr(request, '_start_time'):
                    duration = (timezone.now() - request._start_time).total_seconds()
                else:
                    duration = 0
                
                # Create audit log
                AuditService.log_action(
                    user=request.user,
                    gym=request.current_gym or request.user.gym,
                    action_type=AuditLog.ActionType.VIEW,
                    action=f"API Request: {request.method} {request.path}",
                    model_name='API',
                    object_id=str(request.user.id),
                    object_repr=f"{request.method} {request.path}",
                    changes={'duration': duration, 'status': response.status_code},
                    ip_address=self.get_client_ip(request),
                    user_agent=request.META.get('HTTP_USER_AGENT', '')
                )
            except Exception as e:
                logger.error(f"Failed to log audit: {e}")
        
        return response
    
    def get_client_ip(self, request):
        """Get client IP address"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip


class ExceptionMiddleware(MiddlewareMixin):
    """
    Middleware to handle exceptions globally
    """
    
    def process_exception(self, request, exception):
        """Handle exceptions and return proper response"""
        logger.exception(f"Unhandled exception: {exception}")
        
        # Return JSON response for API requests
        if request.path.startswith('/api/'):
            return JsonResponse({
                'error': 'Internal server error',
                'detail': str(exception) if settings.DEBUG else 'An error occurred'
            }, status=500)
        
        return None


class CorsMiddleware(MiddlewareMixin):
    """
    Custom CORS middleware for additional headers
    """
    
    def process_response(self, request, response):
        """Add CORS headers"""
        response['Access-Control-Allow-Origin'] = '*'
        response['Access-Control-Allow-Methods'] = 'GET, POST, PUT, PATCH, DELETE, OPTIONS'
        response['Access-Control-Allow-Headers'] = 'Content-Type, Authorization, X-Gym-ID'
        
        if request.method == 'OPTIONS':
            response['Access-Control-Max-Age'] = '86400'
            response.status_code = 200
        
        return response