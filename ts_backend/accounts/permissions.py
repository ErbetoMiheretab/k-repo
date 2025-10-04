from rest_framework import permissions


class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Permission to only allow owners of an object or admins to edit it.
    """
    
    def has_object_permission(self, request, view, obj):
        # Read permissions for authenticated users
        if request.method in permissions.SAFE_METHODS:
            return request.user.is_authenticated
        
        # Write permissions only for the owner or admin
        return (
            obj == request.user or 
            request.user.user_type == 'ADMIN'
        )


class CanManageDepartment(permissions.BasePermission):
    """
    Permission for department management operations.
    """
    
    def has_permission(self, request, view):
        return request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        # Admins can manage any department
        if request.user.user_type == 'ADMIN':
            return True
        
        # Team leaders can manage their own departments
        if hasattr(obj, 'team_leader'):
            return obj.team_leader == request.user
        
        return False


class IsTeamLeaderOrReadOnly(permissions.BasePermission):
    """
    Permission for team leaders and admins.
    """
    
    def has_permission(self, request, view):
        if not request.user.is_authenticated:
            return False

        is_admin = request.user.user_type == 'ADMIN'
        is_team_leader = request.user.managed_departments.exists()

        return is_admin or is_team_leader
    
    def has_object_permission(self, request, view, obj):
        return (
        request.user.user_type == 'ADMIN' or
        obj.department in request.user.managed_departments.all()
        )
