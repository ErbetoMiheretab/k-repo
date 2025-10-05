from rest_framework import serializers
from django.contrib.auth import get_user_model
from .models import Category, Tag, TroubleshootingEntry

User = get_user_model()


class UserBasicSerializer(serializers.ModelSerializer):
    """Basic user info for nested serialization"""
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name']
        read_only_fields = ['id', 'username', 'first_name', 'last_name']


class CategorySerializer(serializers.ModelSerializer):
    subcategories = serializers.SerializerMethodField()
    entry_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Category
        fields = [
            'id', 'name', 'slug', 'description', 'parent', 
            'is_active', 'order', 'created_at', 'updated_at',
            'subcategories', 'entry_count'
        ]
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at']
    
    def get_subcategories(self, obj):
        if hasattr(obj, 'subcategories'):
            return CategorySerializer(
                obj.subcategories.filter(is_active=True), 
                many=True, 
                context=self.context
            ).data
        return []
    
    def get_entry_count(self, obj):
        return obj.entries.filter(status='PUBLISHED').count()

    def validate_parent(self, value):
        """Prevent circular relationships"""
        if value and self.instance:
            # Check if setting this parent would create a circular reference
            current = value
            while current and current.parent:
                if current.parent == self.instance:
                    raise serializers.ValidationError(
                        "Cannot set parent: would create circular relationship"
                    )
                current = current.parent
        return value


class TagSerializer(serializers.ModelSerializer):
    entry_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Tag
        fields = [
            'id', 'name', 'slug', 'description', 'is_featured', 
            'created_at', 'entry_count'
        ]
        read_only_fields = ['id', 'slug', 'created_at']
    
    def get_entry_count(self, obj):
        return obj.entries.filter(status='PUBLISHED').count()


class TroubleshootingEntryListSerializer(serializers.ModelSerializer):
    """Lighter serializer for list views"""
    author = UserBasicSerializer(read_only=True)
    category = serializers.StringRelatedField()
    tags = serializers.StringRelatedField(many=True)
    verified_by = UserBasicSerializer(read_only=True)
    vote_score = serializers.SerializerMethodField()
    total_votes = serializers.SerializerMethodField()
    
    class Meta:
        model = TroubleshootingEntry
        fields = [
            'id', 'title', 'slug', 'problem_description', 'category',
            'tags', 'author', 'priority', 'status', 'is_verified',
            'verified_by', 'estimated_time', 'created_at', 'updated_at',
            'vote_score', 'total_votes'
        ]
        read_only_fields = [
            'id', 'slug', 'author', 'verified_by', 'verified_at',
            'created_at', 'updated_at'
        ]
    
    def get_vote_score(self, obj):
        if hasattr(obj, 'score'):
            return obj.score
        return obj.vote_score
    
    def get_total_votes(self, obj):
        if hasattr(obj, 'up_count') and hasattr(obj, 'down_count'):
            return obj.up_count + obj.down_count
        return obj.total_votes


class TroubleshootingEntryDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for detail views"""
    author = UserBasicSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    verified_by = UserBasicSerializer(read_only=True)
    vote_score = serializers.SerializerMethodField()
    total_votes = serializers.SerializerMethodField()
    
    # Write-only fields for updates
    category_id = serializers.IntegerField(write_only=True, required=False)
    tag_ids = serializers.ListField(
        child=serializers.IntegerField(),
        write_only=True,
        required=False
    )
    
    class Meta:
        model = TroubleshootingEntry
        fields = [
            'id', 'title', 'slug', 'problem_description', 'solution',
            'steps_to_reproduce', 'environment_details', 'error_messages',
            'prerequisites', 'estimated_time', 'category', 'category_id',
            'tags', 'tag_ids', 'author', 'priority', 'status',
            'is_verified', 'verified_by', 'verified_at', 'verification_notes',
            'created_at', 'updated_at', 'vote_score', 'total_votes'
        ]
        read_only_fields = [
            'id', 'slug', 'author', 'is_verified', 'verified_by', 
            'verified_at', 'verification_notes', 'created_at', 'updated_at'
        ]
    
    def get_vote_score(self, obj):
        if hasattr(obj, 'score'):
            return obj.score
        return obj.vote_score
    
    def get_total_votes(self, obj):
        if hasattr(obj, 'up_count') and hasattr(obj, 'down_count'):
            return obj.up_count + obj.down_count
        return obj.total_votes
    
    def validate_category_id(self, value):
        """Validate category exists and is active"""
        try:
            category = Category.objects.get(id=value, is_active=True)
            return value
        except Category.DoesNotExist:
            raise serializers.ValidationError("Invalid category or category is not active")
    
    def validate_tag_ids(self, value):
        """Validate all tag IDs exist"""
        if value:
            existing_tags = Tag.objects.filter(id__in=value).count()
            if existing_tags != len(value):
                raise serializers.ValidationError("One or more tag IDs are invalid")
        return value
    
    def validate_estimated_time(self, value):
        """Validate estimated time is reasonable"""
        if value and value > 10080:  # 1 week in minutes
            raise serializers.ValidationError("Estimated time cannot exceed 1 week (10080 minutes)")
        return value
    
    def update(self, instance, validated_data):
        # Handle category update
        category_id = validated_data.pop('category_id', None)
        if category_id:
            instance.category_id = category_id
        
        # Handle tags update
        tag_ids = validated_data.pop('tag_ids', None)
        
        # Update other fields
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        
        instance.save()
        
        # Update tags if provided
        if tag_ids is not None:
            instance.tags.set(tag_ids)
        
        return instance


class TroubleshootingEntryCreateSerializer(serializers.ModelSerializer):
    """Serializer for creating new entries"""
    category_id = serializers.IntegerField()
    tag_ids = serializers.ListField(
        child=serializers.IntegerField(),
        required=False,
        allow_empty=True
    )
    
    class Meta:
        model = TroubleshootingEntry
        fields = [
            'title', 'problem_description', 'solution',
            'steps_to_reproduce', 'environment_details', 'error_messages',
            'prerequisites', 'estimated_time', 'category_id', 'tag_ids',
            'priority', 'status'
        ]
    
    def validate_category_id(self, value):
        """Validate category exists and is active"""
        try:
            Category.objects.get(id=value, is_active=True)
            return value
        except Category.DoesNotExist:
            raise serializers.ValidationError("Invalid category or category is not active")
    
    def validate_tag_ids(self, value):
        """Validate all tag IDs exist"""
        if value:
            existing_tags = Tag.objects.filter(id__in=value).count()
            if existing_tags != len(value):
                raise serializers.ValidationError("One or more tag IDs are invalid")
        return value
    
    def validate_estimated_time(self, value):
        """Validate estimated time is reasonable"""
        if value and value > 10080:  # 1 week in minutes
            raise serializers.ValidationError("Estimated time cannot exceed 1 week (10080 minutes)")
        return value
    
    def create(self, validated_data):
        tag_ids = validated_data.pop('tag_ids', [])
        category_id = validated_data.pop('category_id')
        
        # Set the author from the request context
        validated_data['author'] = self.context['request'].user
        validated_data['category_id'] = category_id
        
        entry = TroubleshootingEntry.objects.create(**validated_data)
        
        # Set tags
        if tag_ids:
            entry.tags.set(tag_ids)
        
        return entry


class TroubleshootingEntryVerificationSerializer(serializers.ModelSerializer):
    """Serializer for entry verification by staff"""
    
    class Meta:
        model = TroubleshootingEntry
        fields = ['is_verified', 'verification_notes']
    
    def validate(self, attrs):
        """Ensure user can verify entries"""
        request = self.context.get('request')
        if not (request and request.user.is_staff):
            raise serializers.ValidationError("Only staff members can verify entries")
        return attrs
    
    def update(self, instance, validated_data):
        if validated_data.get('is_verified'):
            validated_data['verified_by'] = self.context['request'].user
            from django.utils import timezone
            validated_data['verified_at'] = timezone.now()
        else:
            validated_data['verified_by'] = None
            validated_data['verified_at'] = None
        
        return super().update(instance, validated_data)