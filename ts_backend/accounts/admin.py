# In users/admin.py

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Department, UserExpertise

# Customize the User model display in the admin
class CustomUserAdmin(UserAdmin):
    # Add your custom fields to the admin display and forms
    list_display = ('username', 'email', 'first_name', 'last_name', 'role', 'department', 'is_staff')
    list_filter = ('role', 'is_staff', 'is_superuser', 'groups')
    
    # Add custom fields to the edit form (fieldsets)
    # This adds a new section called 'Custom Info' to the user change page
    fieldsets = UserAdmin.fieldsets + (
        ('Custom Info', {'fields': ('role', 'department', 'employee_id', 'phone', 'profile_picture', 'is_verified')}),
    )

# Register your models
admin.site.register(User, CustomUserAdmin)
admin.site.register(Department)
admin.site.register(UserExpertise)