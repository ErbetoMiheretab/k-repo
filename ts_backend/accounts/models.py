from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator
import uuid

from jsonschema import ValidationError


class Department(models.Model):
    DEPARTMENTS =[
        ('DEPARTMENT', 'department'),
        ('DATABASE AND SOFTWARE DEVELOPMNET', 'database and software development'),
        ('CYBER SECURITY', 'cyber security'),
        ('NETWORK' , 'network'),
        ('TRAINING AND MAINTENANCE', 'training and maintenance')
    ]

    department = models.CharField(max_length=100, choices=DEPARTMENTS, default='DEPARTMENT')
    description = models.TextField(blank=True)
    team_leader = models.ForeignKey('User', null=True, blank=True, on_delete=models.SET_NULL, related_name='managed_departments')
    employees = models.ManyToManyField('User', related_name='departments', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Departments'
    
    def __str__(self):
        return self.get_department_display() 
  

class User(AbstractUser):
    USER_TYPES= [
        ('ADMIN', 'Administrator'),
        ('SENIOR_TECH', 'Senior Technician'),
        ('TECH', 'Technician'),
        ('JUNIOR_TECH', 'Junior Technician'),
        ('VIEWER', 'Viewer'),
    ]
    ROLE_CHOICES = [
        ('IT', 'it'),
        ('SYSTEM ADMIN', 'system admin'),
        ('SOFTWARE MAINTENANCE', 'software maintenance'),
        ('DATABASE ADMIN', 'database admin'),
        ('CYBER SECURITY', 'cyber security'),
        ('NETWORK ADMIN', 'network admin'),
        ('WEBSITE ADMIN', 'website admin'),
        ('TECHNOLOGY TRAINING OFFICER', 'technology training officer'),
        ('HARDWARE MAINTENANCE', 'hardware maintenance'),
        ('DATACENTER', 'datacenter'),
    ]

    employee_id = models.UUIDField(db_index=True, unique=True,default=uuid.uuid4, editable=False)
    department = models.ForeignKey(Department, on_delete=models.SET_NULL, null=True, blank=True,  related_name='members')
    user_type = models.CharField(max_length=15, choices=USER_TYPES , default='VIEWER')
    role= models.CharField(max_length=50,choices=ROLE_CHOICES,default='IT')
    phone_number = models.CharField(max_length=20, blank=True, validators=[RegexValidator(r'^\+?1?\d{9,15}$')])
    profile_picture = models.ImageField(upload_to='profile_pictures/', null=True, blank=True)

    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date_joined']

    def clean(self):
        """Add validation logic"""
        if self.user_types == 'ADMIN' and not self.is_superuser:
            raise ValidationError('Admin users must be superusers')
    
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()
    
        def save(self, *args, **kwargs):
        # Ensure username is lowercase for consistency
            if self.username:
                self.username = self.username.lower()
            super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_full_name()} ({self.username})"

class UserExpertise(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='expertise_areas')
    category = models.ForeignKey('troubleshoots.Category', on_delete=models.CASCADE)
    
    class Meta:
        unique_together = ['user', 'category']




# Suggestions for Enhancement
# Custom Manager or QuerySet: Add methods like User.objects.verified() or UserExpertise.objects.by_category(cat) for cleaner queries.

# Signals: Use Django signals to auto-create related objects or log verification events.


# Admin Display: Customize list_display in your admin to show employee_id, role, and is_verified.