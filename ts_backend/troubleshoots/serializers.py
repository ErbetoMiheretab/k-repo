from rest_framework import serializers
from django.contrib.auth import get_user_model
from django.db import transaction
from .models import (
    Category,
    Tag,
    TroubleshootingEntry,
    EntryRevision,
    Attachment,
    Vote,
    Comment,
)

User = get_user_model()


class UserSerializer(serializers.ModelSerializer):
    """Basic user serializer for nested representations"""
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name']
        read_only_fields = ['id']


class CategorySerializer(serializers.ModelSerializer):
    """Serializer for Category model"""
    total_entries = serializers.ReadOnlyField()
    subcategories = serializers.SerializerMethodField()
    parent_name = serializers.CharField(source='parent.name', read_only=True)
    
    class Meta:
        model = Category
        fields = [
            'id', 'name', 'slug', 'description', 'parent', 'parent_name',
            'is_active', 'order', 'total_entries', 'subcategories',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at']
    
    def get_subcategories(self, obj):
        """Get subcategories for this category"""
        subcategories = obj.subcategories.filter(is_active=True)
        return CategorySerializer(subcategories, many=True, context=self.context).data


class TagSerializer(serializers.ModelSerializer):
    """Serializer for Tag model"""
    usage_count = serializers.ReadOnlyField()
    
    class Meta:
        model = Tag
        fields = [
            'id', 'name', 'slug', 'description', 'is_featured',
            'usage_count', 'created_at'
        ]
        read_only_fields = ['id', 'slug', 'created_at']


class AttachmentSerializer(serializers.ModelSerializer):
    """Serializer for Attachment model"""
    uploaded_by = UserSerializer(read_only=True)
    file_url = serializers.SerializerMethodField()
    
    class Meta:
        model = Attachment
        fields = [
            'id', 'file', 'file_url', 'original_filename', 'file_type',
            'file_size', 'mime_type', 'description', 'uploaded_by',
            'uploaded_at'
        ]
        read_only_fields = ['id', 'original_filename', 'file_size', 'uploaded_at']
    
    def get_file_url(self, obj):
        """Get the full URL for the file"""
        if obj.file:
            request = self.context.get('request')
            if request:
                return request.build_absolute_uri(obj.file.url)
            return obj.file.url
        return None


class VoteSerializer(serializers.ModelSerializer):
    """Serializer for Vote model"""
    user = UserSerializer(read_only=True)
    
    class Meta:
        model = Vote
        fields = [
            'id', 'troubleshooting_entry', 'user', 'vote_type',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']
    
    def validate(self, data):
        """Ensure user can only vote once per entry"""
        user = self.context['request'].user
        entry = data['troubleshooting_entry']
        
        # Check if updating existing vote
        if self.instance:
            return data
            
        # Check if user already voted on this entry
        existing_vote = Vote.objects.filter(
            user=user,
            troubleshooting_entry=entry
        ).first()
        
        if existing_vote:
            raise serializers.ValidationError(
                "You have already voted on this entry. Use PUT to update your vote."
            )
        
        return data


class CommentSerializer(serializers.ModelSerializer):
    """Serializer for Comment model"""
    author = UserSerializer(read_only=True)
    replies = serializers.SerializerMethodField()
    replies_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Comment
        fields = [
            'id', 'troubleshooting_entry', 'parent', 'author', 'content',
            'is_solution', 'is_edited', 'is_deleted', 'replies', 'replies_count',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'author', 'is_edited', 'created_at', 'updated_at']
    
    def get_replies(self, obj):
        """Get replies to this comment"""
        if obj.replies.exists():
            replies = obj.replies.filter(is_deleted=False)
            return CommentSerializer(replies, many=True, context=self.context).data
        return []
    
    def get_replies_count(self, obj):
        """Get count of replies"""
        return obj.replies.filter(is_deleted=False).count()


class EntryRevisionSerializer(serializers.ModelSerializer):
    """Serializer for EntryRevision model"""
    revised_by = UserSerializer(read_only=True)
    
    class Meta:
        model = EntryRevision
        fields = [
            'id', 'entry', 'revised_by', 'title', 'problem_description',
            'solution', 'change_summary', 'revision_number', 'created_at'
        ]
        read_only_fields = ['id', 'revised_by', 'revision_number', 'created_at']


class TroubleshootingEntryListSerializer(serializers.ModelSerializer):
    """Lightweight serializer for listing entries"""
    author = UserSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    verified_by = UserSerializer(read_only=True)
    comments_count = serializers.SerializerMethodField()
    user_vote = serializers.SerializerMethodField()
    
    class Meta:
        model = TroubleshootingEntry
        fields = [
            'id', 'title', 'slug', 'problem_description', 'priority',
            'status', 'category', 'tags', 'author', 'is_verified',
            'verified_by', 'upvotes_count', 'downvotes_count',
            'comments_count', 'user_vote', 'estimated_time',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'slug', 'created_at', 'updated_at']
    
    def get_comments_count(self, obj):
        """Get count of comments"""
        return obj.comments.filter(is_deleted=False).count()
    
    def get_user_vote(self, obj):
        """Get current user's vote on this entry"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            vote = obj.votes.filter(user=request.user).first()
            return vote.vote_type if vote else None
        return None


class TroubleshootingEntryDetailSerializer(serializers.ModelSerializer):
    """Detailed serializer for single entry view"""
    author = UserSerializer(read_only=True)
    category = CategorySerializer(read_only=True)
    tags = TagSerializer(many=True, read_only=True)
    verified_by = UserSerializer(read_only=True)
    attachments = AttachmentSerializer(many=True, read_only=True)
    comments = serializers.SerializerMethodField()
    revisions = EntryRevisionSerializer(many=True, read_only=True)
    user_vote = serializers.SerializerMethodField()
    
    class Meta:
        model = TroubleshootingEntry
        fields = [
            'id', 'title', 'slug', 'problem_description', 'solution',
            'steps_to_reproduce', 'environment_details', 'error_messages',
            'prerequisites', 'estimated_time', 'category', 'tags',
            'author', 'priority', 'status', 'is_verified', 'verified_by',
            'verified_at', 'verification_notes', 'upvotes_count',
            'downvotes_count', 'attachments', 'comments', 'revisions',
            'user_vote', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'slug', 'author', 'upvotes_count', 'downvotes_count',
            'created_at', 'updated_at'
        ]
    
    def get_comments(self, obj):
        """Get top-level comments (not replies)"""
        comments = obj.comments.filter(parent=None, is_deleted=False)
        return CommentSerializer(comments, many=True, context=self.context).data
    
    def get_user_vote(self, obj):
        """Get current user's vote on this entry"""
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            vote = obj.votes.filter(user=request.user).first()
            return vote.vote_type if vote else None
        return None


class TroubleshootingEntryCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating entries"""
    tag_names = serializers.ListField(
        child=serializers.CharField(max_length=50),
        write_only=True,
        required=False
    )
    
    class Meta:
        model = TroubleshootingEntry
        fields = [
            'id', 'title', 'problem_description', 'solution',
            'steps_to_reproduce', 'environment_details', 'error_messages',
            'prerequisites', 'estimated_time', 'category', 'tag_names',
            'priority', 'status'
        ]
        read_only_fields = ['id']
    
    def create(self, validated_data):
        """Create entry with tags"""
        tag_names = validated_data.pop('tag_names', [])
        
        with transaction.atomic():
            # Set the author
            validated_data['author'] = self.context['request'].user
            entry = TroubleshootingEntry.objects.create(**validated_data)
            
            # Handle tags
            if tag_names:
                tags = []
                for tag_name in tag_names:
                    tag, created = Tag.objects.get_or_create(
                        name=tag_name.strip(),
                        defaults={'slug': tag_name.strip().lower().replace(' ', '-')}
                    )
                    tags.append(tag)
                entry.tags.set(tags)
            
            return entry
    
    def update(self, instance, validated_data):
        """Update entry with revision tracking"""
        tag_names = validated_data.pop('tag_names', None)
        
        with transaction.atomic():
            # Create revision before updating
            EntryRevision.objects.create(
                entry=instance,
                revised_by=self.context['request'].user,
                title=instance.title,
                problem_description=instance.problem_description,
                solution=instance.solution,
                change_summary=f"Updated on {instance.updated_at}"
            )
            
            # Update the entry
            for attr, value in validated_data.items():
                setattr(instance, attr, value)
            instance.save()
            
            # Handle tags
            if tag_names is not None:
                tags = []
                for tag_name in tag_names:
                    tag, created = Tag.objects.get_or_create(
                        name=tag_name.strip(),
                        defaults={'slug': tag_name.strip().lower().replace(' ', '-')}
                    )
                    tags.append(tag)
                instance.tags.set(tags)
            
            return instance


class VoteCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating/updating votes"""
    
    class Meta:
        model = Vote
        fields = ['troubleshooting_entry', 'vote_type']
    
    def create(self, validated_data):
        """Create or update vote"""
        user = self.context['request'].user
        entry = validated_data['troubleshooting_entry']
        vote_type = validated_data['vote_type']
        
        with transaction.atomic():
            vote, created = Vote.objects.update_or_create(
                user=user,
                troubleshooting_entry=entry,
                defaults={'vote_type': vote_type}
            )
            
            # Update vote counts on the entry
            upvotes = entry.votes.filter(vote_type='UP').count()
            downvotes = entry.votes.filter(vote_type='DOWN').count()
            
            TroubleshootingEntry.objects.filter(id=entry.id).update(
                upvotes_count=upvotes,
                downvotes_count=downvotes
            )
            
            return vote


class CommentCreateUpdateSerializer(serializers.ModelSerializer):
    """Serializer for creating and updating comments"""
    
    class Meta:
        model = Comment
        fields = [
            'troubleshooting_entry', 'parent', 'content', 'is_solution'
        ]
    
    def create(self, validated_data):
        """Create comment with author"""
        validated_data['author'] = self.context['request'].user
        return Comment.objects.create(**validated_data)
    
    def update(self, instance, validated_data):
        """Update comment and mark as edited"""
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.is_edited = True
        instance.save()
        return instance