from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
import uuid



class Department(models.Model):
    """
    Represents organizational departments with team leadership structure.
    """
    DEPARTMENTS =[
        ('DEPARTMENT', 'General Department'),
        ('DATABASE_AND_SOFTWARE_DEV', 'Database and Software Development'),
        ('CYBER_SECURITY', 'Cyber Security'),
        ('NETWORK' , 'Network'),
        ('TRAINING_AND_MAINTENANCE', 'Training and maintenance')
    ]

    name = models.CharField(max_length=100, choices=DEPARTMENTS, default='DEPARTMENT', help_text="Select the department type", db_index=True)
    # department = models.CharField(max_length=100, choices=DEPARTMENTS, default='DEPARTMENT')
    description = models.TextField(blank=True,
                                   help_text="Brief description of the department's responsibilities")
    team_leader = models.ForeignKey('User', null=True, blank=True, on_delete=models.SET_NULL, related_name='managed_departments')
    # employees = models.ManyToManyField('User', related_name='departments', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']
        verbose_name_plural = 'Departments'
        indexes = [
            models.Index(fields=['name']),
            models.Index(fields=['team_leader']),
        ]
    
    def __str__(self):
        return self.get_name_display() 
    @property
    def member_count(self):
        """Return the number of members in this department."""
        return self.members.count()
    
    def clean(self):
        """Validate department data."""
        super().clean()
        if self.team_leader and self.team_leader.department != self:
            if hasattr(self, 'pk') and self.pk:  # Only for existing departments
                raise ValidationError(
                    "Team leader must be a member of this department"
                )

            """avoids hasattr() check because self.pk will be none if not set"""
            # if self.pk and self.team_leader and self.team_leader.department != self:
            #     raise ValidationError("Team leader must be a member of this department")

  

class User(AbstractUser):
    USER_TYPES= [
        ('ADMIN', 'Administrator'),
        ('SENIOR_TECH', 'Senior Technician'),
        ('TECH', 'Technician'),
        ('JUNIOR_TECH', 'Junior Technician'),
        ('VIEWER', 'Viewer'),
    ]
    ROLE_CHOICES = [
        ('IT', 'IT Specialist'),
        ('SYSTEM_ADMIN', 'System Administrator'),
        ('SOFTWARE_MAINTENANCE', 'Software Maintenance'),
        ('DATABASE_ADMIN', 'Database Admin'),
        ('CYBER_SECURITY', 'Cyber Security'),
        ('NETWORK_ADMIN', 'Network Administrator'),
        ('WEBSITE_ADMIN', 'Website Administrator'),
        ('TECHNOLOGY_TRAINING_OFFICER', 'Technology Training Officer'),
        ('HARDWARE_MAINTENANCE', 'Hardware Maintenance'),
        ('DATACENTER', 'Datacenter'),
    ]

    employee_id = models.UUIDField(
        db_index=True, unique=True,default=uuid.uuid4, editable=False)
    department = models.ForeignKey(
        Department, on_delete=models.SET_NULL,
          null=True, blank=True,  related_name='members'
          )
    user_type = models.CharField(
        max_length=15, choices=USER_TYPES,
        default='VIEWER',
        db_index=True,
        help_text="User's permission level in the system")
    role= models.CharField(max_length=50,choices=ROLE_CHOICES,default='IT',
                            help_text="User's functional role in the organization",
        db_index=True)
    phone_number = models.CharField(max_length=20, blank=True, 
            validators=[RegexValidator(
            r'^\+?1?\d{9,15}$',
            message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed."
        )])
    profile_picture = models.ImageField(upload_to='profile_pictures/', null=True, blank=True)

    is_verified = models.BooleanField(default=False,
                                      help_text="Whether the user account has been verified by an administrat")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-date_joined']
        indexes = [
            models.Index(fields=['employee_id']),
            models.Index(fields=['department']),
            models.Index(fields=['user_type']),
            models.Index(fields=['role']),
            models.Index(fields=['is_verified']),
        ]

    def clean(self):
        """Validate user data."""
        super().clean()
        if self.user_type == 'ADMIN' and not self.is_superuser:
            raise ValidationError('Admin users must be superusers')
        
        if self.email and User.objects.filter(
            email=self.email
        ).exclude(pk=self.pk).exists():
            raise ValidationError('Email address must be unique')
        
    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip()
    
    def save(self, *args, **kwargs):
    # Ensure username is lowercase for consistency
        if self.username:
            self.username = self.username.lower()

        if self.user_type == 'ADMIN':
            self.is_superuser = True
            self.is_staff = True

        super().save(*args, **kwargs)



    def __str__(self):
        return f"{self.get_full_name()} ({self.username})"

    def get_permissions_display(self):
        """Return human-readable permissions level."""
        return dict(self.USER_TYPES).get(self.user_type, self.user_type)
    
    def can_manage_department(self, department):
        """Check if user can manage the given department."""
        return self.managed_departments.filter(pk=department.pk).exists()



# Suggestions for Enhancement
# Custom Manager or QuerySet: Add methods like User.objects.verified() or UserExpertise.objects.by_category(cat) for cleaner queries.

# Signals: Use Django signals to auto-create related objects or log verification events.


# Admin Display: Customize list_display in your admin to show employee_id, role, and is_verified.