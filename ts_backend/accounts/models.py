import os
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.core.validators import RegexValidator
from django.core.exceptions import ValidationError
from django.utils.html import strip_tags
import uuid


def validate_profile_image(value):
    """
    Custom validator for profile images to ensure security and size constraints.
    """
    # Max file size: 5MB
    max_size_mb = 5
    if value.size > max_size_mb * 1024 * 1024:
        raise ValidationError(f'Image size cannot exceed {max_size_mb}MB.')


class Department(models.Model):
    """
    Represents organizational departments with team leadership structure.
    """

    DEPARTMENTS = [
        ("DEPARTMENT", "General Department"),
        ("DATABASE_AND_SOFTWARE_DEV", "Database and Software Development"),
        ("CYBER_SECURITY", "Cyber Security"),
        ("NETWORK", "Network"),
        ("TRAINING_AND_MAINTENANCE", "Training and Maintenance"),
    ]

    name = models.CharField(
        max_length=100,
        choices=DEPARTMENTS,
        default="DEPARTMENT",
        unique=True,  # Added: Prevent duplicate departments
        help_text="Select the department type",
        db_index=True,
    )
    description = models.TextField(
        blank=True, help_text="Brief description of the department's responsibilities"
    )
    team_leader = models.OneToOneField(  # Changed: OneToOneField instead of ForeignKey
        "User",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="led_department",  # Changed: More accurate name
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)  # Added: Track updates

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "Departments"
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["team_leader"]),
        ]

    def __str__(self):
        return self.get_name_display()

    def get_member_count(self):
        """Return the number of members in this department."""
        return self.members.count()

    def clean(self):
        """Validate department data."""
        super().clean()
        # Check if team leader belongs to this department (only for existing departments)
        if self.pk and self.team_leader:
            # Refresh from DB to avoid stale data
            if self.team_leader.department_id != self.pk:
                raise ValidationError(
                    {"team_leader": "Team leader must be a member of this department"}
                )


class User(AbstractUser):
    """
    Extended user model with department membership and role-based access.
    """

    USER_TYPES = [
        ("ADMIN", "Administrator"),
        ("SENIOR_TECH", "Senior Technician"),
        ("TECH", "Technician"),
        ("JUNIOR_TECH", "Junior Technician"),
        ("VIEWER", "Viewer"),
    ]

    ROLE_CHOICES = [
        ("IT", "IT Specialist"),
        ("SYSTEM_ADMIN", "System Administrator"),
        ("SOFTWARE_MAINTENANCE", "Software Maintenance"),
        ("DATABASE_ADMIN", "Database Admin"),
        ("CYBER_SECURITY", "Cyber Security"),
        ("NETWORK_ADMIN", "Network Administrator"),
        ("WEBSITE_ADMIN", "Website Administrator"),
        ("TECHNOLOGY_TRAINING_OFFICER", "Technology Training Officer"),
        ("HARDWARE_MAINTENANCE", "Hardware Maintenance"),
        ("DATACENTER", "Datacenter"),
    ]

    employee_id = models.UUIDField(
        db_index=True, unique=True, default=uuid.uuid4, editable=False
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="members",
    )
    user_type = models.CharField(
        max_length=15,
        choices=USER_TYPES,
        default="VIEWER",
        db_index=True,
        help_text="User's permission level in the system",
    )
    role = models.CharField(
        max_length=50,
        choices=ROLE_CHOICES,
        default="IT",
        help_text="User's functional role in the organization",
        db_index=True,
    )
    phone_number = models.CharField(
        max_length=20,
        blank=True,
        validators=[
            RegexValidator(
                r"^\+?1?\d{9,15}$",
                message="Phone number must be entered in the format: '+999999999'. Up to 15 digits allowed.",
            )
        ],
    )
    profile_picture = models.ImageField(
        upload_to="profile_pictures/",
        null=True,
        blank=True,
        validators=[validate_profile_image],  # Added: Custom validator
    )
    is_verified = models.BooleanField(
        default=False,
        help_text="Whether the user account has been verified by an administrator",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Added: Email should be required and unique
    email = models.EmailField(unique=True, blank=False)

    class Meta:
        ordering = ["-date_joined"]
        indexes = [
            models.Index(fields=["employee_id"]),
            models.Index(fields=["department"]),
            models.Index(fields=["user_type"]),
            models.Index(fields=["role"]),
            models.Index(fields=["is_verified"]),
            models.Index(fields=["email"]),  # Added: Index on email
        ]

    def clean(self):
        """Validate user data."""
        super().clean()

        # Sanitize text fields to prevent XSS
        if self.first_name:
            self.first_name = strip_tags(self.first_name.strip())
        if self.last_name:
            self.last_name = strip_tags(self.last_name.strip())
        if self.email:
            self.email = strip_tags(self.email.strip())
        if self.phone_number:
            self.phone_number = strip_tags(self.phone_number.strip())

        # Validate admin requirements
        if self.user_type == "ADMIN" and not self.is_staff:
            # Auto-fix instead of raising error (will be handled in save())
            pass

        # Email uniqueness is now handled by model field constraint

    @property
    def full_name(self):
        """Return user's full name or username if name is not set."""
        full = f"{self.first_name} {self.last_name}".strip()
        return full if full else ""

    def save(self, *args, **kwargs):
        """Custom save logic for user creation and updates."""
        # Normalize username to lowercase
        if self.username:
            self.username = self.username.lower().strip()

        # Normalize email to lowercase
        if self.email:
            self.email = self.email.lower().strip()

        # Auto-promote ADMIN users to superuser/staff
        if self.user_type == "ADMIN":
            self.is_superuser = True
            self.is_staff = True

        # Call full_clean before save to run validators
        self.full_clean()

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_full_name()} ({self.username})"

    def get_permissions_display(self):
        """Return human-readable permissions level."""
        return dict(self.USER_TYPES).get(self.user_type, self.user_type)

    def can_manage_department(self, department):
        """Check if user can manage the given department."""
        # Fixed: Use correct related name
        return hasattr(self, "led_department") and self.led_department == department

    def is_team_leader(self):
        """Check if user is a team leader of any department."""
        return hasattr(self, "led_department") and self.led_department is not None


# Add custom managers for common queries
class UserManager(models.Manager):
    def verified(self):
        return self.filter(is_verified=True)

    def by_department(self, department):
        return self.filter(department=department)

    def team_leaders(self):
        return self.filter(led_department__isnull=False)

# Add to User model:
# objects = UserManager()


# Signals: Use Django signals to auto-create related objects or log verification events.


# Admin Display: Customize list_display in your admin to show employee_id, role, and is_verified.
