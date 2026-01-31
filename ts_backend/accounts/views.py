from rest_framework.renderers import JSONRenderer
import logging
from rest_framework import viewsets, status, generics
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.pagination import PageNumberPagination
from rest_framework.exceptions import ValidationError, NotFound, PermissionDenied
from django.utils.html import strip_tags

from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.auth import get_user_model
from django.db.models import Count, Prefetch
from django.core.exceptions import ObjectDoesNotExist, ValidationError as DjangoValidationError
from django.db import transaction

from .models import Department
from .serializers import (
    DepartmentSerializer,
    UserSerializer,
    UserCreateSerializer,
    UserProfileSerializer,
    ChangePasswordSerializer,
    CustomTokenObtainPairSerializer,
)
from .permissions import IsTeamLeaderOrReadOnly


# Configure logger
logger = logging.getLogger(__name__)

User = get_user_model()


class StandardPagination(PageNumberPagination):
    page_size = 15
    page_size_query_param = "page_size"
    max_page_size = 100


class DepartmentViewSet(viewsets.ModelViewSet):
    """
     ViewSet for viewing and editing departments.

    Provides CRUD operations for departments with proper permissions
    and optimized database queries.

    Endpoints:
    - list: GET /api/departments/
    - create: POST /api/departments/
    - retrieve: GET /api/departments/{id}/
    - update: PUT /api/departments/{id}/
    - partial_update: PATCH /api/departments/{id}/
    - destroy: DELETE /api/departments/{id}/
    - members: GET /api/departments/{id}/members/
    - my_managed: GET /api/departments/my_managed/
    """

    serializer_class = DepartmentSerializer
    renderer_classes = [JSONRenderer]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = ["team_leader", "name"]
    search_fields = ["name", "description"]
    ordering_fields = ["name", "created_at", "member_count"]
    ordering = ["name"]
    pagination_class = StandardPagination

    def get_queryset(self):
        """Optimized queryset with prefetch for better performance."""
        return (
            Department.objects.select_related("team_leader", "team_leader__department")
            .prefetch_related(
                Prefetch(
                    "members",
                    queryset=User.objects.select_related("department").order_by(
                        "first_name", "last_name"
                    ),
                )
            )
            .annotate(member_count=Count("members"))
        )

    def get_permissions(self):
        """
        Returns the list of permissions required for the current action.
        Admins have full access.
        Team leaders can update members in their department.
        Authenticated users can view
        """
        if self.action in ["create", "destroy"]:
            permission_classes = [IsAdminUser]
        elif self.action in ["update", "partial_update"]:
            permission_classes = [IsAuthenticated, IsTeamLeaderOrReadOnly]
        else:  # list, retrieve, custom actions
            permission_classes = [IsAuthenticated]

        return [permission() for permission in permission_classes]

    @action(detail=True, methods=["get"], permission_classes=[IsAuthenticated])
    def members(self, request, pk=None):
        """
        Get all members of a specific department.
        """
        try:
            department = self.get_object()
            members = department.members.select_related("department").order_by(
                "first_name", "last_name"
            )

            # Apply pagination
            page = self.paginate_queryset(members)
            if page is not None:
                serializer = UserSerializer(page, many=True, context={"request": request})
                return self.get_paginated_response(serializer.data)
            serializer = UserSerializer(members, many=True, context={"request": request})
            return Response(serializer.data)
        except Exception as e:
            logger.error(f"Error retrieving department members: {str(e)}", exc_info=True)
            return Response(
                {"error": "An error occurred while retrieving department members"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def my_managed(self, request):
        """
        Get departments managed by the current user.
        """
        if hasattr(request.user, "led_department") and request.user.led_department:
            department = self.get_queryset().get(pk=request.user.led_department.pk)
            serializer = self.get_serializer(department)
            return Response(serializer.data)
        return Response(
            {"detail": "You are not leading any department"},
            status=status.HTTP_404_NOT_FOUND,
        )

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def assign_leader(self, request, pk=None):
        """
        Assign a team leader to a department.

        Expects: {"user_id": <user_id>}
        """
        department = self.get_object()
        user_id = request.data.get("user_id")

        if not user_id:
            return Response(
                {"error": "user_id is required"}, status=status.HTTP_400_BAD_REQUEST
            )
        try:
            user = User.objects.get(pk=user_id)
        except User.DoesNotExist:
            return Response(
                {"error": "User not found"}, status=status.HTTP_404_NOT_FOUND
            )
        # Validate user can be team leader
        if user.user_type not in ["ADMIN", "SENIOR_TECH"]:
            return Response(
                {"error": "User must be Admin or Senior Technician"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if user is in this department
        if user.department != department:
            return Response(
                {"error": "User must be a member of this department"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        department.team_leader = user
        department.save()

        serializer = self.get_serializer(department)
        return Response(serializer.data)


class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for viewing and editing users with role-based access control.

     Provides CRUD operations for users. Only admins can create/edit users.

    Endpoints:
    - list: GET /api/users/
    - create: POST /api/users/
    - retrieve: GET /api/users/{id}/
    - update: PUT /api/users/{id}/
    - partial_update: PATCH /api/users/{id}/
    - destroy: DELETE /api/users/{id}/
    - me: GET /api/users/me/
    - verify: POST /api/users/{id}/verify/
    - unverify: POST /api/users/{id}/unverify/
    """

    permission_classes = [IsAdminUser]
    renderer_classes = [JSONRenderer]
    filter_backends = [DjangoFilterBackend, SearchFilter, OrderingFilter]
    filterset_fields = [
        "department",
        "role",
        "is_verified",
        "user_type",
    ]  # Filter by department, role, etc.
    search_fields = [
        "username",
        "email",
        "employee_id",
        "first_name",
        "last_name",
    ]  # Search key fields
    ordering_fields = ["first_name", "last_name", "created_at"]
    ordering = ["first_name", "last_name"]
    pagination_class = StandardPagination

    def get_queryset(self):
        """Optimized queryset with related data."""
        return User.objects.select_related(
            "department", "led_department"
        ).prefetch_related("department__members")

    def get_serializer_class(self):
        """Return appropriate serializer based on action."""
        if self.action == "create":
            return UserCreateSerializer
        return UserSerializer

    def get_permissions(self):
        """
        Custom permissions per action.
        'me' action allows authenticated users.
        """
        if self.action == "me":
            permission_classes = [IsAuthenticated]
        else:
            permission_classes = [IsAdminUser]

        return [permission() for permission in permission_classes]

    @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
    def me(self, request):
        """
        Get current user profile with optimized query.
        """
        try:
            user = self.get_queryset().get(pk=request.user.pk)
            serializer = UserSerializer(user, context={"request": request})
            return Response(serializer.data)
        except User.DoesNotExist:
            logger.error(f"User with ID {request.user.pk} does not exist", exc_info=True)
            return Response(
                {"error": "User not found"},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            logger.error(f"Error retrieving user profile: {str(e)}", exc_info=True)
            return Response(
                {"error": "An error occurred while retrieving user profile"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def verify(self, request, pk=None):
        """
        Verify a user account.
        """
        try:
            user = self.get_object()

            if user.is_verified:
                return Response(
                    {"detail": "User is already verified"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            user.is_verified = True
            user.save(update_fields=["is_verified"])
            serializer = self.get_serializer(user)
            logger.info(f"User {user.username} verified by admin {request.user.username}")
            return Response(
                {"detail": "User verified successfully", "user": serializer.data}
            )
        except Exception as e:
            logger.error(f"Error verifying user: {str(e)}", exc_info=True)
            return Response(
                {"error": "An error occurred while verifying user"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=["post"], permission_classes=[IsAdminUser])
    def unverify(self, request, pk=None):
        """
        Unverify a user account.
        """
        try:
            user = self.get_object()

            if not user.is_verified:
                return Response(
                    {"detail": "User is already unverified"},
                    status=status.HTTP_400_BAD_REQUEST,
                )

            user.is_verified = False
            user.save(update_fields=["is_verified"])
            serializer = self.get_serializer(user)
            logger.info(f"User {user.username} unverified by admin {request.user.username}")
            return Response(
                {"detail": "User unverified successfully", "user": serializer.data}
            )
        except Exception as e:
            logger.error(f"Error unverifying user: {str(e)}", exc_info=True)
            return Response(
                {"error": "An error occurred while unverifying user"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

        @action(detail=False, methods=["get"], permission_classes=[IsAuthenticated])
        def team_leaders(self, request):
            """
            Get all users who are team leaders.
            """
            leaders = self.get_queryset().filter(led_department__isnull=False)

            page = self.paginate_queryset(leaders)
            if page is not None:
                serializer = self.get_serializer(page, many=True)
                return self.get_paginated_response(serializer.data)

            serializer = self.get_serializer(leaders, many=True)
            return Response(serializer.data)


class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    View for the current user to retrieve and update their profile.

    Users can only update limited fields (name, email, phone, picture).
    """

    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated]

    def get_object(self):
        """Return the current user with optimized query."""
        try:
            user = User.objects.select_related("department").get(pk=self.request.user.pk)
            return user
        except User.DoesNotExist:
            logger.error(f"User with ID {self.request.user.pk} does not exist", exc_info=True)
            raise NotFound("User not found")

    def update(self, request, *args, **kwargs):
        """Override to add success message."""
        try:
            # Log the profile update attempt
            logger.info(f"User {request.user.username} attempting to update profile")

            # Sanitize input data to prevent XSS
            sanitized_data = {}
            for key, value in request.data.items():
                if isinstance(value, str):
                    sanitized_data[key] = strip_tags(value.strip())
                else:
                    sanitized_data[key] = value

            # Create a mutable copy of the request data
            request._full_data = sanitized_data

            response = super().update(request, *args, **kwargs)
            response.data = {
                "detail": "Profile updated successfully",
                "user": response.data,
            }
            logger.info(f"User {request.user.username} profile updated successfully")
            return response
        except ValidationError as e:
            logger.warning(f"Validation error during profile update for user {request.user.username}: {str(e)}")
            return Response(
                {"error": "Invalid data provided", "details": e.detail},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error updating profile for user {request.user.username}: {str(e)}", exc_info=True)
            return Response(
                {"error": "An error occurred while updating profile"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class ChangePasswordView(generics.UpdateAPIView):
    """
    An endpoint for changing password.

    Requires: old_password, new_password, confirm_new_password
    """

    serializer_class = ChangePasswordSerializer
    permission_classes = [IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def get_object(self, queryset=None):
        """Return the current user."""
        return self.request.user

    def update(self, request, *args, **kwargs):
        """Handle password update with proper validation."""

        try:
            # Log the password change attempt
            logger.info(f"User {request.user.username} attempting to change password")

            serializer = self.get_serializer(
                instance=self.object, data=request.data, context={"request": request}
            )
            serializer.is_valid(
                raise_exception=True
            )  # Will raise ValidationError if old_password is wrong
            serializer.save()

            logger.info(f"Password updated successfully for user {request.user.username}")
            return Response(
                {"detail": "Password updated successfully"}, status=status.HTTP_200_OK
            )
        except ValidationError as e:
            logger.warning(f"Validation error during password change for user {request.user.username}: {str(e)}")
            return Response(
                {"error": "Invalid data provided", "details": e.detail},
                status=status.HTTP_400_BAD_REQUEST
            )
        except Exception as e:
            logger.error(f"Error changing password for user {request.user.username}: {str(e)}", exc_info=True)
            return Response(
                {"error": "An error occurred while changing password"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class CustomTokenObtainPairView(TokenObtainPairView):
    """
    Custom JWT token endpoint with additional user information.

    Returns access and refresh tokens plus user details.
    """

    serializer_class = CustomTokenObtainPairSerializer
    throttle_classes = [AnonRateThrottle]


class MyDepartmentMembersView(generics.ListAPIView):
    """
    View for a team leader to see all members of their department.

    - Admins can see all users
    - Team leaders see their department members only
    - Other users get empty results
    """

    serializer_class = UserSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [SearchFilter, OrderingFilter]
    search_fields = ["username", "email", "first_name", "last_name"]
    ordering_fields = ["first_name", "last_name", "created_at"]
    ordering = ["first_name", "last_name"]
    pagination_class = StandardPagination

    def get_queryset(self):
        """
        Return users from departments managed by the current user.
        """
        user = self.request.user

        # Admin users can see all users
        if user.user_type == "ADMIN":
            return User.objects.select_related("department").all()

        # Team leaders can see their department members
        if hasattr(user, "led_department") and user.led_department:
            return User.objects.select_related("department").filter(
                department=user.led_department
            )

        # Return empty queryset for non-leaders
        return User.objects.none()

    def list(self, request, *args, **kwargs):
        """Override to add department context."""
        queryset = self.filter_queryset(self.get_queryset())
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            response_data = {
                "department": None,
                "count": self.paginator.page.paginator.count,
                "results": serializer.data,
            }

            # Add department info for team leaders
            if hasattr(request.user, "led_department") and request.user.led_department:
                response_data["department"] = {
                    "id": request.user.led_department.id,
                    "name": request.user.led_department.get_name_display(),
                    "member_count": request.user.led_department.member_count,
                }

            return self.get_paginated_response(response_data)

        serializer = self.get_serializer(queryset, many=True)
        response_data = {"members": serializer.data}

        # Add department info
        if hasattr(request.user, "led_department") and request.user.led_department:
            response_data["department"] = {
                "id": request.user.led_department.id,
                "name": request.user.led_department.get_name_display(),
            }

        return Response(response_data)
