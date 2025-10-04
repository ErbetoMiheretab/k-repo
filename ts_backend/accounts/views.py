from rest_framework.renderers import JSONRenderer
from rest_framework import viewsets, status, permissions, generics
from rest_framework.response import Response
from rest_framework.decorators import action
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.throttling import AnonRateThrottle, UserRateThrottle
from rest_framework.pagination import PageNumberPagination

from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.auth import get_user_model
from django.db.models import Count, Prefetch

from .models import Department
from .serializers import (
      DepartmentSerializer,
    UserSerializer,
    UserCreateSerializer,
    UserProfileSerializer,
    ChangePasswordSerializer,
    CustomTokenObtainPairSerializer
)
from .permissions import IsTeamLeaderOrReadOnly


User = get_user_model()



class StandardPagination(PageNumberPagination):
    page_size = 15


class DepartmentViewSet(viewsets.ModelViewSet):
    """
     ViewSet for viewing and editing departments.

    Provides CRUD operations for departments with proper permissions
    and optimized database queries.
    """

    serializer_class = DepartmentSerializer
    renderer_classes = [JSONRenderer]
    filter_backends = [DjangoFilterBackend,SearchFilter, OrderingFilter]
    filterset_fields = ['team_leader', 'name'] # Filter by team_leader ID
    search_fields = ['name', 'description'] # Search by name and description
    ordering_fields = ['name', 'created_at']
    ordering= ['name']
    pagination_class = StandardPagination
    # queryset = Department.objects.all().order_by('name')
    # queryset = Department.objects.annotate(
    #     member_count_annotation=Count('members')
    # ).order_by('name')

    def get_queryset(self):
        """Optimized queryset with prefetch for better performance."""
        return Department.objects.select_related('team_leader').prefetch_related(
            Prefetch(
                'members',
                queryset=User.objects.select_related('department')
            )
        ).annotate(
            member_count_annotation=Count('members')
        )
    

    def get_permissions(self):
        """
        Returns the list of permissions required for the current action.
        Admins have full access.
        Team leaders can update members in their department.
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            if self.request.user.is_superuser:
                self.permission_classes = [IsAdminUser]
            else:
                self.permission_classes = [IsTeamLeaderOrReadOnly]
        else:  # list, retrieve
            self.permission_classes = [IsAuthenticated]
        return super().get_permissions()
  

    @action(detail=True, methods=['get'], permission_classes=[IsAuthenticated])
    def members(self, request, pk=None):
        """
        Get all members of a specific department.
        """
        department = self.get_object()
        members = department.members.select_related('department').all()
        serializer = UserSerializer(members, many=True, context={'request': request})
        return Response(serializer.data)

    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def my_managed(self, request):
        """
        Get departments managed by the current user.
        """
        departments = self.get_queryset().filter(team_leader=request.user)
        serializer = self.get_serializer(departments, many=True)
        return Response(serializer.data) 



class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for viewing and editing users with role-based access control.

    Provides different serializers.
    """

    permission_classes = [permissions.IsAdminUser] # Only admins can manage users
    renderer_classes = [JSONRenderer]
    filter_backends = [DjangoFilterBackend,SearchFilter, OrderingFilter]
    filterset_fields = ['department', 'role', 'is_verified', 'user_type'] # Filter by department, role, etc.
    search_fields = ['username', 'email', 'employee_id', 'first_name', 'last_name'] # Search key fields
    ordering_fields = ['first_name', 'last_name', 'created_at']
    ordering = ['first_name', 'last_name']
    pagination_class = StandardPagination
    # queryset = User.objects.all().order_by('first_name', 'last_name')
    
    def get_queryset(self):
        """Optimized queryset with related data."""
        return User.objects.select_related('department').prefetch_related(
            'managed_departments'
        )

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        return UserSerializer
    
    @action(detail=False, methods=['get'], permission_classes=[IsAuthenticated])
    def me(self, request):
        """
        Get current user profile with optimized query.
        """
        user = User.objects.select_related('department').prefetch_related(
            'managed_departments'
        ).get(pk=request.user.pk)
        serializer = UserSerializer(user, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def verify(self, request, pk=None):
        """
        Verify a user account.
        """
        user = self.get_object()
        user.is_verified = True
        user.save()
        return Response({'detail': 'User verified successfully'})

    @action(detail=True, methods=['post'], permission_classes=[IsAdminUser])
    def unverify(self, request, pk=None):
        """
        Unverify a user account.
        """
        user = self.get_object()
        user.is_verified = False
        user.save()
        return Response({'detail': 'User unverified successfully'})


class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    View for the current user to retrieve and update their profile.
    """
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        """Return the current user with optimized query."""
        return User.objects.select_related('department').get(pk=self.request.user.pk)

class ChangePasswordView(generics.UpdateAPIView):
    """
    An endpoint for changing password.
    """
    serializer_class = ChangePasswordSerializer
    model = User
    permission_classes = [permissions.IsAuthenticated]
    throttle_classes = [UserRateThrottle]

    def get_object(self, queryset=None):
        
        # Return the current user.
        return self.request.user
    

    def update(self, request, *args, **kwargs):
        #Handle password update with proper validation

        self.object = self.get_object()
        serializer = self.get_serializer(instance=self.object,
                                         data=request.data,
                                         context={'request': request})
        serializer.is_valid(raise_exception=True) # Will raise ValidationError if old_password is wrong
        serializer.save() 

        return Response(
            {"detail": "Password updated successfully"},
              status=status.HTTP_200_OK)



class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    throttle_classes = [AnonRateThrottle]


class MyDepartmentMembersView(generics.ListAPIView):
    """
    View for a team leader to see all members of the departments they manage.
    """
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        Return users from departments managed by the current user.
        """
        user = self.request.user
        
        # Admin users can see all users
        if user.user_type == 'ADMIN':
            return User.objects.select_related('department').all()
        
        # Team leaders can see their department members
        return User.objects.select_related('department').filter(
            department__team_leader=user
        )

    def list(self, request, *args, **kwargs):
        """Override to add department context."""
        response = super().list(request, *args, **kwargs)
        
        # Add managed departments info
        managed_deps = request.user.managed_departments.values('id', 'name')
        response.data = {
            'managed_departments': list(managed_deps),
            'members': response.data
        }
        return response

