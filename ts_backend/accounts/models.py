from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator

class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    manager = models.ForeignKey('User', null=True, blank=True, on_delete=models.SET_NULL, related_name='managed_departments')
    created_at = models.DateTimeField(auto_now_add=True)
    
    def __str__(self):
        return self.name

class User(AbstractUser):
    ROLE_CHOICES = [
        ('ADMIN', 'Administrator'),
        ('SENIOR_TECH', 'Senior Technician'),
        ('TECH', 'Technician'),
        ('JUNIOR_TECH', 'Junior Technician'),
        ('VIEWER', 'Viewer'),
    ]
    
    employee_id = models.CharField(max_length=20, unique=True, null=True, blank=True)
    department = models.ForeignKey(Department, null=True, blank=True, on_delete=models.SET_NULL)
    role = models.CharField(max_length=15, choices=ROLE_CHOICES, default='TECH')
    phone = models.CharField(max_length=20, blank=True, validators=[RegexValidator(r'^\+?1?\d{9,15}$')])
    profile_picture = models.ImageField(upload_to='profile_pictures/', null=True, blank=True)
    
    # Reputation system
    reputation_score = models.IntegerField(default=0)
    total_solutions = models.PositiveIntegerField(default=0)
    total_helpful_votes = models.PositiveIntegerField(default=0)
    
    # Preferences
    email_notifications = models.BooleanField(default=True)
    push_notifications = models.BooleanField(default=True)
    
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.get_full_name()} ({self.username})"

class UserExpertise(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='expertise_areas')
    category = models.ForeignKey('troubleshooting.Category', on_delete=models.CASCADE)
    verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(User, null=True, blank=True, on_delete=models.SET_NULL, related_name='verified_expertise')
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ['user', 'category']