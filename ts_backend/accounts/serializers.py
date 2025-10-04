from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
# from django.contrib.auth import get_user_model
from . models import Department, User



class DepartmentSerializer(serializers.ModelSerializer):
    team_leader_name = serializers.CharField(
        source='team_leader.get_full_name', read_only=True)
    member_count = serializers.IntegerField(source='member_count_annotation', read_only=True)
    members = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    
    class Meta:
        model = Department
        fields = ['id', 'name', 'description', 'team_leader',  'team_leader_name', 
                 'member_count', 'created_at', 'members']
        read_only_fields = ['created_at']

    def to_representation(self, instance):
        representation = super().to_representation(instance)

        # Convert department code to human-readable format
        representation['name_display'] = instance.get_name_display()
        return representation
    
    def validate_team_leader(self, value):
        """Validate that team leader has appropriate permissions."""
        if value and value.user_type not in ['ADMIN', 'SENIOR_TECH']:
            raise serializers.ValidationError(
                "Team leader must be an Admin or Senior Technician"
            )
        return value


class UserSerializer(serializers.ModelSerializer):
    department_name = serializers.SerializerMethodField()
    # department_name = serializers.CharField(
    #     source='department.get_department_display', read_only=True)
    full_name = serializers.CharField(
        source='get_full_name', read_only=True)
    managed_departments = DepartmentSerializer(many=True, read_only=True)
    user_type_display = serializers.CharField(source='get_role_display', read_only=True)

    role_display = serializers.CharField(
        source='get_role_display', 
        read_only=True
    )
    permissions_display = serializers.CharField(
        source='get_permissions_display', 
        read_only=True
    )


    def get_department_name(self, obj):
        return obj.department.get_name_display() if obj.department else None



    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 
                 'employee_id', 'department', 'department_name','user_type', 'user_type_display' ,'role', 
                 'phone_number', 'profile_picture', 'is_verified', 'permissions_display',
                 'managed_departments', 'created_at', 'updated_at', 'full_name', 'role_display']
        
        read_only_fields = ['created_at', 'updated_at', 'employee_id']
        
        extra_kwargs = {
            'password': {'write_only': True, 'required': False},
        }   


    def create(self, validated_data):
        password = validated_data.pop('password', None)
        if not password:
            raise serializers.ValidationError("Password is required to create a user.")

        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        return user

    
    def update(self, instance, validated_data):
        if 'password' in validated_data:
            password = validated_data.pop('password')
            instance.set_password(password)
        return super().update(instance, validated_data)
    
    def validate_email(self, value):
        """Ensure email uniqueness."""
        if value and User.objects.filter(
            email=value
        ).exclude(pk=self.instance.pk if self.instance else None).exists():
            raise serializers.ValidationError("Email address must be unique")
        return value

class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User

        fields = ['username', 'email', 'password','confirm_password' ,'first_name', 'last_name', 'user_type'
                , 'department', 'role', 'phone_number']
    

    def validate(self, attrs):
        """Validate password confirmation."""
        if attrs['password'] != attrs['confirm_password']:
            raise serializers.ValidationError("Passwords don't match")
        attrs.pop('confirm_password')
        return attrs

    username = serializers.CharField()

    def validate_username(self, value):
        value = value.lower()
        if User.objects.filter(username=value).exists():
            raise serializers.ValidationError("Username already exists")
        return value

    
    def create(self, validated_data):
       return User.objects.create_user(**validated_data)



class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile updates"""
    # department_name = serializers.CharField('department.get_name_display', read_only=True)
    department_name = serializers.SerializerMethodField()
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    
    def get_department_name(self, obj):
        return obj.department.get_name_display() if obj.department else None
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email',
                'phone_number', 'profile_picture', 'department', 'username', 'department_name', 'full_name']

        read_only_fields = ['username', 'department']

    def validate_email(self, value):
        """Ensure email uniqueness for profile updates."""
        if value and User.objects.filter(
            email=value
        ).exclude(pk=self.instance.pk).exists():
            raise serializers.ValidationError("Email address is already in use")
        return value




class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True, required=True)
    new_password = serializers.CharField(write_only=True,
                                          required=True,
                                        min_length=8,
                 help_text="Password must be at least 8 characters long" )
    confirm_new_password = serializers.CharField(write_only=True, required=True)


    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect")
        return value
    
    def validate(self, attrs):
        """Validate new password confirmation."""
        if attrs['new_password'] != attrs['confirm_new_password']:
            raise serializers.ValidationError("New passwords don't match")
        return attrs
    
    def update(self, instance, validated_data):
        instance.set_password(validated_data['new_password'])
        instance.save()
        return instance
       
    # You need to override create for Serializer, even if you don't use it
    def create(self, validated_data):
        raise NotImplementedError("Create method not supported")

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['employee_id'] = str(user.employee_id)
        token['user_type'] = user.user_type
        token['role'] = user.role
        return token
    
    def validate(self, attrs):
        data = super().validate(attrs)
        data.update({
            'employee_id': str(self.user.employee_id),
            'user_type': self.user.user_type,
            'role': self.user.role,
            'full_name': self.user.get_full_name(),
        })
        return data