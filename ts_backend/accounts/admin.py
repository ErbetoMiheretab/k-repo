from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.utils.html import format_html
from .models import User, Department


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    """
    Enhanced admin interface for Department model.
    """
    list_per_page = 15
    list_display = ['name_display','team_leader', 'member_count', 'created_at']
    list_filter = ['name', 'created_at']
    search_fields = ['name', 'description', 'team_leader__username']
    readonly_fields = ['created_at']
    
    def member_count(self, obj):
        """Display member count."""
        return obj.members.count()
    member_count.short_description = 'Members'
    
    def get_queryset(self, request):
        """Optimize queryset."""
        return super().get_queryset(request).select_related('team_leader')
    
    def name_display(self, obj):
        return obj.get_name_display()
    name_display.short_description = 'Department'


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    """
    Enhanced admin interface for User model with custom fields.
    """
    list_per_page = 15

    list_display = [
        'username', 'email', 'first_name', 'last_name', 
        'role', 'department', 'user_type', 'is_verified', 
        'is_staff', 'created_at'
    ]
    list_filter = [
        'role', 'user_type', 'is_verified', 'is_staff', 
        'is_superuser', 'department', 'created_at'
    ]
    search_fields = [
        'username', 'email', 'first_name', 'last_name', 
        'employee_id'
    ]
    readonly_fields = ['employee_id', 'created_at', 'updated_at']
    
    fieldsets = UserAdmin.fieldsets + (
        ('Organization Info', {
            'fields': (
                'employee_id', 'department', 'role', 'user_type', 
                'phone_number', 'profile_picture', 'is_verified'
            )
        }),
        ('Timestamps', {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    add_fieldsets = UserAdmin.add_fieldsets + (
        ('Organization Info', {
            'fields': (
                'department', 'role', 'user_type', 'phone_number', 
                'is_verified'
            )
        }),
    )
    
    def get_queryset(self, request):
        """Optimize queryset with related data."""
        return super().get_queryset(request).select_related('department')
    
    def save_model(self, request, obj, form, change):
        """
        Custom save logic.

        Automatically sets `is_verified=True` for users created via the Django admin.
        This bypasses standard verification workflows and is intended only for trusted internal staff.
        Ensure this behavior is reviewed during audits or when onboarding new admins.
        """
        if not change: 
            obj.is_verified = True 
        super().save_model(request, obj, form, change)

    actions = ['verify_users', 'unverify_users']
    
    def verify_users(self, request, queryset):
        """Bulk verify users."""
        updated = queryset.update(is_verified=True)
        self.message_user(request, f'{updated} users were verified.')
    verify_users.short_description = "Verify selected users"
    
    def unverify_users(self, request, queryset):
        """Bulk unverify users."""
        updated = queryset.update(is_verified=False)
        self.message_user(request, f'{updated} users were unverified.')
    unverify_users.short_description = "Unverify selected users"