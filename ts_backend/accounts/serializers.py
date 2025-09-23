from rest_framework import serializers
from django.contrib.auth import get_user_model
from . models import Department, UserExpertise


User = get_user_model()

class DepartmentSerializer(serializers.ModelSerializer):
    team_leader_name = serializers.CharField(source='team_leader.get_full_name', read_only=True)
    member_count = serializers.SerializerMethodField()

    class Meta:
        model = Department
        fields = ['id', 'name', 'description', 'team_leader', 'team_leader_name', 
                 'member_count', 'created_at']
        read_only_fields = ['created_at']

        def get_member_count(self, obj):
            return obj.user_set.count()


class UserSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)
    expertise_areas = serializers.SerializerMethodField()
    managed_departments = DepartmentSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 
                 'employee_id', 'department', 'department_name', 'role', 
                 'phone', 'profile_picture', 'is_verified', 'is_active',
                 'expertise_areas', 'managed_departments', 'created_at', 'updated_at']
        read_only_fields = ['created_at', 'updated_at']
        extra_kwargs = {
            'password': {'write_only': True},
        }   
    
    def get_expertise_areas(self, obj):
        return UserExpertiseSerializer(obj.expertise_areas.all(), many=True).data

    def create(self, validated_data):
        password = validated_data.pop('password', None)
        user = User.objects.create_user(**validated_data)
        if password:
            user.set_password(password)
            user.save()
        return user
    
    def update(self, instance, validated_data):
        password = validated_data.pop('password', None)
        user = super().update(instance, validated_data)


class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User

    ields = ['username', 'email', 'password', 'first_name', 'last_name',
                 'employee_id', 'department', 'role', 'phone']
    
    def create(self, validated_data):
        password = validated_data.pop('password')
        user = User.objects.create_user(**validated_data)
        user.set_password(password)
        user.save()
        return user


class UserExpertiseSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    verified_by_name = serializers.CharField(source='verified_by.get_full_name', read_only=True)


    class Meta:
        model = UserExpertise
        fields = ['id', 'user', 'user_name', 'category', 'category_name', 
                 'verified', 'verified_by', 'verified_by_name', 'created_at']
        read_only_fields = ['created_at']

class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile updates"""
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone', 'profile_picture']

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=8)
    
    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect")
        return value