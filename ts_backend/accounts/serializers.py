from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer
from django.contrib.auth import get_user_model
from . models import Department, UserExpertise, User


# User = get_user_model()


class DepartmentSerializer(serializers.ModelSerializer):
    team_leader_name = serializers.CharField(source='team_leader.get_full_name', read_only=True)
    member_count = serializers.IntegerField(source='member_count_annotaion', read_only=True)

    class Meta:
        model = Department
        fields = ['id', 'name', 'description', 'team_leader',  'team_leader_name', 
                 'member_count', 'created_at']
        read_only_fields = ['created_at']

    # def get_member_count(self, obj):
    #     return obj.user_set.count()


class UserSerializer(serializers.ModelSerializer):
    department_name = serializers.CharField(source='department.name', read_only=True)
    expertise_areas = serializers.SerializerMethodField()
    full_name = serializers.CharField(source='get_full_name', read_only=True)
    managed_departments = DepartmentSerializer(many=True, read_only=True)

    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 
                 'employee_id', 'department', 'department_name', 'role', 
                 'phone', 'profile_picture', 'is_verified',
                 'expertise_areas', 'managed_departments', 'created_at', 'updated_at', 'full_name']
        read_only_fields = ['created_at', 'updated_at']
        extra_kwargs = {
            'password': {'write_only': True, 'required': False},
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
        if 'password' in validated_data:
            password = validated_data.pop('password')
            instance.set_password(password)
        return super().update(instance, validated_data)

class UserCreateSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User

        fields = ['username', 'email', 'password', 'first_name', 'last_name',
                    'employee_id', 'department', 'role', 'phone']
    
    # def create(self, validated_data):
    #     password = validated_data.pop('password')
    #     user = User.objects.create_user(**validated_data)
    #     user.set_password(password)
    #     user.save()
    #     return user

    def create(self, validated_data):
       return User.objects.create_user(**validated_data)



class UserExpertiseSerializer(serializers.ModelSerializer):
    user_name = serializers.CharField(source='user.get_full_name', read_only=True)
    category_name = serializers.CharField(source='category.name', read_only=True)
    
    class Meta:
        model = UserExpertise
        fields = ['id', 'user', 'user_name', 'category', 'category_name']


class UserProfileSerializer(serializers.ModelSerializer):
    """Serializer for user profile updates"""
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'email', 'phone', 'profile_picture', 'department']

class ChangePasswordSerializer(serializers.Serializer):
    old_password = serializers.CharField(write_only=True, required=True)
    new_password = serializers.CharField(write_only=True, required=True, min_length=8)
    
    def validate_old_password(self, value):
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect")
        return value
    
    def update(self, instance, validated_data):
        instance.set_password(validated_data['new_password'])
        instance.save()
        return instance
       
    # You need to override create for Serializer, even if you don't use it
    def create(self, validated_data):
        raise NotImplementedError()

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token['employee_id'] = user.employee_id

        return token