from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.utils import timezone
from django.db.models import Prefetch
from .models import Category, Tag, TroubleshootingEntry

User = get_user_model()


class CategoryIdValidator:
    def validate_category_id(self, value):
        if not Category.objects.filter(id=value, is_active=True).exists():
            raise serializers.ValidationError("Invalid category or is not active")
        
        return value

class TagIdsValidator:
    def validate_tag_ids(self, value):
        if value:  # empty list is allowed
            found = Tag.objects.filter(id__in=value).count()
            if found != len(value):
                raise serializers.ValidationError("One or more tag IDs are invalid")
        return value

class EstimatedTimeValidator:
    MAX_MINUTES = 7 * 24 * 60  # 1 week

    def validate_estimated_time(self, value):
        if value and value > self.MAX_MINUTES:
            raise serializers.ValidationError(
                f"Estimated time cannot exceed 1 week ({self.MAX_MINUTES} minutes)"
            )
        return value


class UserBasicSerializer(serializers.ModelSerializer):
    """Basic user info for nested serialization"""
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name']
        read_only_fields = fields


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
        ordering = ["order", "name"]

    def get_subcategories(self, obj) -> list[dict]:
        # Prefetch in the viewset guarantees this is already cached
        return CategorySerializer(
            obj.subcategories.all(), many=True, context=self.context
        ).data
    
    def get_entry_count(self, obj):
        return obj.entries.filter(status='PUBLISHED').count()

    # def validate_parent(self, value) -> Category | None:
    #     """Prevent circular relationships"""
    #     if value and self.instance:
    #         # Check if setting this parent would create a circular reference
    #         current = value
    #         while current and current.parent:
    #             if current.parent == self.instance:
    #                 raise serializers.ValidationError(
    #                     "Cannot set parent: would create circular relationship"
    #                 )
    #             current = current.parent
    #     return value

    def validate_parent(self, value: Category | None) -> Category | None:
        if value and self.instance:
            candidate = value
            while candidate and candidate.parent:
                if candidate.parent == self.instance:
                    raise serializers.ValidationError(
                        "Setting this parent would create a circular reference."
                    )
                candidate = candidate.parent
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
    """
    Optimised for list endpoints.
    View-set MUST annotate:
        score        -> vote_score
        total_votes  -> total_votes
    and prefetch category / tags / author / verified_by.
    """
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
    
    # def get_vote_score(self, obj):
    #     if hasattr(obj, 'score'):
    #         return obj.score
    #     return obj.vote_score
    def get_vote_score(self, obj):
        return getattr(obj, "score", 0)  # <-- safe fallback

    
    def get_total_votes(self, obj):
        if hasattr(obj, 'up_count') and hasattr(obj, 'down_count'):
            return obj.up_count + obj.down_count
        return obj.total_votes


class TroubleshootingEntryDetailSerializer(
    serializers.ModelSerializer,
    CategoryIdValidator,
    TagIdsValidator,
    EstimatedTimeValidator
    ):
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
    
    # def get_vote_score(self, obj):
    #     if hasattr(obj, 'score'):
    #         return obj.score
    #     return obj.vote_score
    def get_vote_score(self, obj):
        return getattr(obj, "score", 0)
    
    def get_total_votes(self, obj):
        if hasattr(obj, 'up_count') and hasattr(obj, 'down_count'):
            return obj.up_count + obj.down_count
        return obj.total_votes
    
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


class TroubleshootingEntryCreateSerializer(
    serializers.ModelSerializer,
    CategoryIdValidator, 
    TagIdsValidator,     
    EstimatedTimeValidator 
    ):
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

    def create(self, validated_data) -> TroubleshootingEntry:
        tag_ids = validated_data.pop('tag_ids', [])
        category_id = validated_data.pop('category_id')
        
        # Set the author from the request context
        validated_data['author'] = self.context['request'].user
        validated_data['category_id'] = category_id
        
        entry = TroubleshootingEntry.objects.create(**validated_data)
        entry.tags.set(tag_ids)
        return entry


class TroubleshootingEntryVerificationSerializer(serializers.ModelSerializer):
    """
     **Staff-only endpoint** – enforce `IsAdminUser` in the view-set.
    """
    
    class Meta:
        model = TroubleshootingEntry
        fields = ['is_verified', 'verification_notes']
    
    
    def update(self, instance: TroubleshootingEntry, validated_data: dict) -> TroubleshootingEntry:
        if validated_data.get('is_verified'):
            validated_data['verified_by'] = self.context['request'].user
            validated_data['verified_at'] = timezone.now()
        else:
            validated_data['verified_by'] = None
            validated_data['verified_at'] = None
        
        return super().update(instance, validated_data)