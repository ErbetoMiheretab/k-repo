import os
from PIL import Image
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

# from django.contrib.auth import get_user_model
from .models import Department, User


def validate_image_file(value):
    """
    Validates uploaded image files for security and size constraints.
    """
    if value:
        # Check file size (limit to 5MB)
        max_size_mb = 5
        if value.size > max_size_mb * 1024 * 1024:
            raise serializers.ValidationError(f'Image size cannot exceed {max_size_mb}MB.')

        # Check file extension
        ext = os.path.splitext(value.name)[1].lower()
        valid_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.webp']
        if ext not in valid_extensions:
            raise serializers.ValidationError('Only JPEG, PNG, GIF, and WebP files are allowed.')

        # Verify that the file is actually an image
        try:
            img = Image.open(value)
            img.verify()
        except Exception:
            raise serializers.ValidationError('Uploaded file is not a valid image.')

        # Reset file pointer after verification
        value.seek(0)

    return value


class DepartmentSerializer(serializers.ModelSerializer):
    team_leader_name = serializers.CharField(
        source="team_leader.get_full_name", read_only=True
    )
    team_leader_details = serializers.SerializerMethodField()  # Added: More info
    member_count = serializers.IntegerField(read_only=True)  # Changed: Remove source
    members = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    name_display = serializers.CharField(source="get_name_display", read_only=True)

    class Meta:
        model = Department
        fields = [
            "id",
            "id",
            "name",
            "name_display",
            "description",
            "team_leader",
            "team_leader_name",
            "team_leader_details",
            "member_count",
            "created_at",
            "updated_at",
            "members",
        ]
        read_only_fields = ["created_at", "updated_at", "member_count"]

    def to_representation(self, instance):
        representation = super().to_representation(instance)

        # Convert department code to human-readable format
        representation["name_display"] = instance.get_name_display()
        return representation

    def get_team_leader_details(self, obj):
        """Return basic team leader info."""
        if obj.team_leader:
            return {
                "id": obj.team_leader.id,
                "name": obj.team_leader.get_full_name(),
                "employee_id": str(obj.team_leader.employee_id),
                "role": obj.team_leader.get_role_display(),
            }
        return None

    def validate_team_leader(self, value):
        """Validate that team leader has appropriate permissions."""
        if value:
            # Check user type
            if value.user_type not in ["ADMIN", "SENIOR_TECH"]:
                raise serializers.ValidationError(
                    "Team leader must be an Admin or Senior Technician"
                )

            # Check if user is already leading another department
            if hasattr(value, "led_department") and value.led_department:
                # Allow if updating the same department
                if not self.instance or value.led_department.id != self.instance.id:
                    raise serializers.ValidationError(
                        f"{value.get_full_name()} is already leading {value.led_department.get_name_display()}"
                    )
        return value

    def validate(self, attrs):
        """Validate department data."""
        team_leader = attrs.get("team_leader")
        department = self.instance

        # If updating and team leader is set, validate they're in this department
        if department and team_leader and team_leader.department != department:
            raise serializers.ValidationError(
                {
                    "team_leader": f"{team_leader.get_full_name()} must be a member of this department"
                }
            )

        return attrs


class UserSerializer(serializers.ModelSerializer):
    department_name = serializers.SerializerMethodField()
    department_details = serializers.SerializerMethodField()  # Added
    full_name = serializers.CharField(source="get_full_name", read_only=True)
    led_department = DepartmentSerializer(many=True, read_only=True)
    is_team_leader = serializers.SerializerMethodField(read_only=True)
    user_type_display = serializers.CharField(source="get_role_display", read_only=True)

    role_display = serializers.CharField(source="get_role_display", read_only=True)
    permissions_display = serializers.CharField(
        source="get_permissions_display", read_only=True
    )

    def get_department_name(self, obj):
        """Return department display name."""
        return obj.department.get_name_display() if obj.department else None

    def get_department_details(self, obj):
        """Return detailed department info."""
        if obj.department:
            return {
                "id": obj.department.id,
                "name": obj.department.get_name_display(),
                "team_leader": obj.department.team_leader.get_full_name()
                if obj.department.team_leader
                else None,
            }
        return None

    def get_led_department(self, obj):
        """Return department being led by this user."""
        if hasattr(obj, "led_department") and obj.led_department:
            return {
                "id": obj.led_department.id,
                "name": obj.led_department.get_name_display(),
                "member_count": obj.led_department.member_count,
            }
        return None

    def get_is_team_leader(self, obj):
        """Return whether user is a team leader."""
        return obj.is_team_leader()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "email",
            "first_name",
            "last_name",
            "employee_id",
            "department",
            "department_name",
            "department_details",
            "user_type",
            "user_type_display",
            "role",
            "role_display",
            "phone_number",
            "profile_picture",
            "is_verified",
            "permissions_display",
            "led_department",
            "is_team_leader",
            "created_at",
            "updated_at",
            "full_name",
        ]

        read_only_fields = ["created_at", "updated_at", "employee_id"]

        extra_kwargs = {
            "password": {"write_only": True, "required": False},
            "email": {"required": True},
        }

    def create(self, validated_data):
        password = validated_data.pop("password", None)
        if not password:
            raise serializers.ValidationError("Password is required to create a user.")

        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        return user

    def update(self, instance, validated_data):
        """Handle password updates properly."""
        if "password" in validated_data:
            password = validated_data.pop("password")
            instance.set_password(password)
        return super().update(instance, validated_data)

    def validate_email(self, value):
        """Ensure email uniqueness."""
        if value:
            value = value.lower()  # Normalize email
            qs = User.objects.filter(email=value)
            if self.instance:
                qs = qs.exclude(pk=self.instance.pk)
            if qs.exists():
                raise serializers.ValidationError("Email address is already in use")
        return value

    def validate_department(self, value):
        """Validate department assignment."""
        # If user is a team leader, they can't change their department
        if (
            self.instance
            and hasattr(self.instance, "led_department")
            and self.instance.led_department
        ):
            if value != self.instance.department:
                raise serializers.ValidationError(
                    "Team leaders cannot change their department. "
                    "Please reassign team leadership first."
                )
        return value


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(
        write_only=True, min_length=8, style={"input_type": "password"}
    )
    confirm_password = serializers.CharField(
        write_only=True, min_length=8, style={"input_type": "password"}
    )
    email = serializers.EmailField(required=True)

    class Meta:
        model = User

        fields = [
            "username",
            "email",
            "password",
            "confirm_password",
            "first_name",
            "last_name",
            "user_type",
            "department",
            "role",
            "phone_number",
            "profile_picture",
        ]

    def validate(self, attrs):
        """Validate password confirmation."""
        if attrs["password"] != attrs["confirm_password"]:
            raise serializers.ValidationError("Passwords don't match")
        attrs.pop("confirm_password")

        # Validate team leader constraints
        if attrs.get("user_type") in ["ADMIN", "SENIOR_TECH"] and attrs.get(
            "department"
        ):
            # Check if department already has a team leader
            dept = attrs["department"]
            if dept.team_leader and dept.team_leader.pk:
                # This is just a warning; admin can override
                pass
        return attrs

    def validate_username(self, value):
        """Validate and normalize username."""
        value = value.lower()
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Username already exists")
        return value

    def validate_profile_picture(self, value):
        """Validate profile picture upload."""
        if value:
            return validate_image_file(value)
        return value

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)

    def validate_email(self, value):
        """Validate and normalize email."""
        value = value.lower().strip()
        if User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email already exists")
        return value


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile updates"""

    department_name = serializers.SerializerMethodField()
    department_details = serializers.SerializerMethodField()
    full_name = serializers.CharField(source="get_full_name", read_only=True)
    is_team_leader = serializers.SerializerMethodField(read_only=True)

    def get_department_name(self, obj):
        return obj.department.get_name_display() if obj.department else None

    def get_is_team_leader(self, obj):
        """Return whether user is a team leader."""
        return obj.is_team_leader()

    class Meta:
        model = User
        fields = [
            "id",
            "username",
            "first_name",
            "last_name",
            "email",
            "phone_number",
            "profile_picture",
            "department",
            "department_name",
            "department_details",
            "full_name",
            "role",
            "user_type",
            "is_team_leader",
            "employee_id",
        ]
        read_only_fields = [
            "username",
            "department",
            "role",
            "user_type",
            "employee_id",
            "is_team_leader",
        ]

    def validate_profile_picture(self, value):
        """Validate profile picture upload."""
        if value:
            return validate_image_file(value)
        return value

    def validate_email(self, value):
        """Ensure email uniqueness for profile updates."""
        if (
            value
            and User.objects.filter(email=value).exclude(pk=self.instance.pk).exists()
        ):
            raise serializers.ValidationError("Email address is already in use")
        return value


class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(
        write_only=True, required=True, style={"input_type": "password"}
    )
    new_password = serializers.CharField(
        write_only=True,
        required=True,
        min_length=8,
        help_text="Password must be at least 8 characters long",
    )
    confirm_new_password = serializers.CharField(
        write_only=True, required=True, style={"input_type": "password"}
    )

    def validate_old_password(self, value):
        user = self.context["request"].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect")
        return value

    def validate_new_password(self, value):
        """Validate new password strength."""
        # You can add custom password validation here
        if len(value) < 8:
            raise serializers.ValidationError(
                "Password must be at least 8 characters long"
            )
        return value

    def validate(self, attrs):
        """Validate new password confirmation."""
        if attrs["new_password"] != attrs["confirm_new_password"]:
            raise serializers.ValidationError("New passwords don't match")
        return attrs

    def save(self, **kwargs):
        """Update user password."""
        user = self.context["request"].user
        user.set_password(self.validated_data["new_password"])
        user.save()
        return user


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Custom JWT token with additional user information."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Add custom claims
        token["employee_id"] = str(user.employee_id)
        token["user_type"] = user.user_type
        token["role"] = user.role
        token["is_verified"] = user.is_verified
        token["is_team_leader"] = user.is_team_leader()

        if user.department:
            token["department"] = user.department.get_name_display()

        return token

    def validate(self, attrs):
        """Add user information to token response."""
        data = super().validate(attrs)
        # Check if user is verified
        if not self.user.is_verified:
            raise serializers.ValidationError(
                "Your account is not verified. Please contact an administrator."
            )
        # Add additional user data
        data.update(
            {
                "user": {
                    "id": self.user.id,
                    "employee_id": str(self.user.employee_id),
                    "username": self.user.username,
                    "email": self.user.email,
                    "full_name": self.user.get_full_name(),
                    "user_type": self.user.user_type,
                    "user_type_display": self.user.get_user_type_display(),
                    "role": self.user.role,
                    "role_display": self.user.get_role_display(),
                    "department": self.user.department.get_name_display()
                    if self.user.department
                    else None,
                    "is_verified": self.user.is_verified,
                    "is_team_leader": self.user.is_team_leader(),
                }
            }
        )

        return data
