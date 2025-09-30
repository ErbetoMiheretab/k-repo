from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator



class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    team_leader = models.ForeignKey('User', null=True, blank=True, on_delete=models.SET_NULL, related_name='managed_departments')
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
    
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
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