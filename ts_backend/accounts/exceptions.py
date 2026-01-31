"""
Custom exception handlers for the accounts app.
"""
import logging
from rest_framework.views import exception_handler
from rest_framework.response import Response
from rest_framework import status
from django.core.exceptions import ValidationError as DjangoValidationError
from django.http import Http404
from django.core.exceptions import PermissionDenied

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    Custom exception handler that provides consistent error response format.
    """
    # Call REST framework's default exception handler first
    response = exception_handler(exc, context)

    if response is not None:
        # Standardize error response format
        custom_response_data = {
            'detail': 'An error occurred',
            'status_code': response.status_code
        }

        # Handle different types of errors
        if hasattr(response, 'data'):
            if isinstance(response.data, dict):
                # If there's a 'detail' key, use it
                if 'detail' in response.data:
                    custom_response_data['detail'] = response.data['detail']
                # If there are field errors, include them
                elif any(key not in ['detail', 'status_code'] for key in response.data.keys()):
                    custom_response_data['detail'] = 'Validation error'
                    custom_response_data['errors'] = response.data
                else:
                    custom_response_data['detail'] = str(response.data)
            elif isinstance(response.data, list):
                custom_response_data['detail'] = response.data[0] if response.data else 'An error occurred'
            else:
                custom_response_data['detail'] = str(response.data)

        response.data = custom_response_data

    else:
        # Handle Django exceptions that DRF doesn't handle
        if isinstance(exc, DjangoValidationError):
            logger.warning(f"Django validation error: {str(exc)}")
            response = Response(
                {
                    'detail': 'Validation error',
                    'errors': exc.message_dict if hasattr(exc, 'message_dict') else [str(exc)],
                    'status_code': status.HTTP_400_BAD_REQUEST
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        elif isinstance(exc, Http404):
            logger.warning(f"Not found error: {str(exc)}")
            response = Response(
                {
                    'detail': 'Not found',
                    'status_code': status.HTTP_404_NOT_FOUND
                },
                status=status.HTTP_404_NOT_FOUND
            )
        elif isinstance(exc, PermissionDenied):
            logger.warning(f"Permission denied: {str(exc)}")
            response = Response(
                {
                    'detail': 'Permission denied',
                    'status_code': status.HTTP_403_FORBIDDEN
                },
                status=status.HTTP_403_FORBIDDEN
            )
        else:
            # Log unexpected errors
            logger.error(f"Unexpected error: {str(exc)}", exc_info=True)
            response = Response(
                {
                    'detail': 'An unexpected error occurred',
                    'status_code': status.HTTP_500_INTERNAL_SERVER_ERROR
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    return response


class AccountsAPIException(Exception):
    """Base exception for accounts app API errors."""
    default_detail = 'An error occurred'
    default_code = 'error'
    status_code = status.HTTP_500_INTERNAL_SERVER_ERROR

    def __init__(self, detail=None, code=None, status_code=None):
        if detail is None:
            detail = self.default_detail
        if code is None:
            code = self.default_code
        if status_code is not None:
            self.status_code = status_code

        self.detail = detail
        self.code = code


class UserNotFoundError(AccountsAPIException):
    """Exception raised when a user is not found."""
    default_detail = 'User not found'
    default_code = 'user_not_found'
    status_code = status.HTTP_404_NOT_FOUND


class DepartmentNotFoundError(AccountsAPIException):
    """Exception raised when a department is not found."""
    default_detail = 'Department not found'
    default_code = 'department_not_found'
    status_code = status.HTTP_404_NOT_FOUND


class InvalidUserTypeError(AccountsAPIException):
    """Exception raised when user type is invalid for operation."""
    default_detail = 'Invalid user type for this operation'
    default_code = 'invalid_user_type'
    status_code = status.HTTP_400_BAD_REQUEST


class TeamLeaderAssignmentError(AccountsAPIException):
    """Exception raised when team leader assignment fails."""
    default_detail = 'Team leader assignment failed'
    default_code = 'team_leader_assignment_error'
    status_code = status.HTTP_400_BAD_REQUEST