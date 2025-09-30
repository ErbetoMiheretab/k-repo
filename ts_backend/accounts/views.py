from rest_framework.renderers import JSONRenderer

from rest_framework import viewsets, status, permissions, generics

from rest_framework.response import Response
from rest_framework.filters import SearchFilter, OrderingFilter
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from .serializers import CustomTokenObtainPairSerializer
from rest_framework_simplejwt.views import TokenRefreshView

from django_filters.rest_framework import DjangoFilterBackend
from django.contrib.auth import get_user_model
from django.db.models import Q, Count

from .models import Department, UserExpertise
from .serializers import (
      DepartmentSerializer,
    UserSerializer,
    UserCreateSerializer,
    UserExpertiseSerializer,
    UserProfileSerializer,
    ChangePasswordSerializer
)



User = get_user_model()


class DepartmentViewSet(viewsets.ModelViewSet):
    """
     ViewSet for viewing and editing departments.
    """

    # queryset = Department.objects.all().order_by('name')
    queryset = Department.objects.annotate(
        member_count_annotation=Count('user')
    ).order_by('name')
    serializer_class = DepartmentSerializer
    
    renderer_classes = [JSONRenderer]
    filter_backends = [DjangoFilterBackend,SearchFilter, OrderingFilter]
    filterset_fields = ['team_leader'] # Filter by team_leader ID
    search_fields = ['name', 'description'] # Search by name and description
    ordering_fields = ['name', 'created_at']

  

    def get_permissions(self):
        """
        Instantiates and returns the list of permissions that this view requires.
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            self.permission_classes = [IsAdminUser]
        else: # list, retrieve
            self.permission_classes = [IsAuthenticated]
        return super().get_permissions()    



class UserViewSet(viewsets.ModelViewSet):
    """
    ViewSet for viewing and editing users.
    Provides different serializers for 'create' and other actions.
    """
    queryset = User.objects.all().order_by('first_name', 'last_name')
    permission_classes = [permissions.IsAdminUser] # Only admins can manage users

    renderer_classes = [JSONRenderer]
    filter_backends = [DjangoFilterBackend,SearchFilter, OrderingFilter]
    filterset_fields = ['department', 'role', 'is_verified'] # Filter by department, role, etc.
    search_fields = ['username', 'email', 'employee_id'] # Search key fields
    ordering_fields = ['first_name', 'last_name', 'created_at']

    def get_serializer_class(self):
        if self.action == 'create':
            return UserCreateSerializer
        return UserSerializer

class UserExpertiseViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing user expertise records.
    """
    queryset = UserExpertise.objects.all()
    serializer_class = UserExpertiseSerializer
    permission_classes = [permissions.IsAuthenticated]

    def perform_create(self, serializer):
        # By default, associate the expertise with the requesting user
        serializer.save(user=self.request.user)


    

class UserProfileView(generics.RetrieveUpdateAPIView):
    """
    View for the current user to retrieve and update their profile.
    """
    serializer_class = UserProfileSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        # Returns the currently authenticated user
        return self.request.user

class ChangePasswordView(generics.UpdateAPIView):
    """
    An endpoint for changing password.
    """
    serializer_class = ChangePasswordSerializer
    model = User
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self, queryset=None):
        return self.request.user

    def update(self, request, *args, **kwargs):
        self.object = self.get_object()
        serializer = self.get_serializer(data=request.data)

        # if serializer.is_valid():
        #     # Check old password
        #     if not self.object.check_password(serializer.data.get("old_password")):
        #         return Response({"old_password": ["Wrong password."]}, status=status.HTTP_400_BAD_REQUEST)
            
        #     # set_password also hashes the password that the user will get
        #     self.object.set_password(serializer.data.get("new_password"))
        #     self.object.save()
        #     return Response({"status": "password set successfully"}, status=status.HTTP_200_OK)

        # return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        
        
        serializer.is_valid(raise_exception=True) # Will raise ValidationError if old_password is wrong

        # The serializer's update method will handle saving
        serializer.save() 

        return Response({"detail": "Password updated successfully"}, status=status.HTTP_200_OK)



class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer






# In views.py
class MyDepartmentMembersView(generics.ListAPIView):
    """
    View for a team leader to see all members of the departments they manage.
    """
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        """
        This view should return a list of all users
        for the departments managed by the currently authenticated user.
        """
        user = self.request.user
        # Get all user IDs from all departments the user manages
        managed_departments = user.managed_departments.all()
        return User.objects.filter(department__in=managed_departments).order_by('first_name')