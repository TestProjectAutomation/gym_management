# core/exceptions.py
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ValidationError
from django.db import IntegrityError
import logging

logger = logging.getLogger(__name__)


class GymManagementException(Exception):
    """Base exception for gym management system"""
    pass


class SubscriptionError(GymManagementException):
    """Subscription related errors"""
    pass


class PaymentError(GymManagementException):
    """Payment related errors"""
    pass


class AttendanceError(GymManagementException):
    """Attendance related errors"""
    pass


class PermissionError(GymManagementException):
    """Permission related errors"""
    pass


class TenancyError(GymManagementException):
    """Tenancy isolation errors"""
    pass


def custom_exception_handler(exc, context):
    """
    Custom exception handler for DRF
    """
    response = exception_handler(exc, context)
    
    # Log exception
    logger.error(f"Exception: {exc}", exc_info=True)
    
    # Handle custom exceptions
    if isinstance(exc, GymManagementException):
        return Response(
            {'error': str(exc), 'type': exc.__class__.__name__},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Handle ValidationError
    if isinstance(exc, ValidationError):
        return Response(
            {'error': exc.messages, 'type': 'ValidationError'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Handle IntegrityError
    if isinstance(exc, IntegrityError):
        return Response(
            {'error': 'Database integrity error', 'detail': str(exc)},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Handle PermissionError
    if isinstance(exc, PermissionError):
        return Response(
            {'error': str(exc)},
            status=status.HTTP_403_FORBIDDEN
        )
    
    # If response is None, return a custom response
    if response is None:
        return Response(
            {'error': 'Internal server error', 'detail': str(exc)},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR
        )
    
    # Add custom error code to response
    if hasattr(exc, 'code'):
        response.data['code'] = exc.code
    
    return response