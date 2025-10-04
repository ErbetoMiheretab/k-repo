from django.db import models
from django.db.models import Count
from django.contrib.auth import get_user_model
from django.contrib.postgres.search import SearchVector
from django.core.validators import (
    MinValueValidator,
    MaxValueValidator,
    FileExtensionValidator,
)
from django.contrib.postgres.search import SearchVectorField
from django.contrib.postgres.indexes import GinIndex
from django.utils.text import slugify
import os


User = get_user_model()


class Category(models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=100, unique=True)
    description = models.TextField(blank=True)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="subcategories",
    )
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ["order", "name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    # status
    # @property
    # def total_entries(self):
    #     return self.entries.count()

    def __str__(self):
        return self.name


class Tag(models.Model):
    name = models.CharField(max_length=50, unique=True)
    slug = models.SlugField(max_length=50, unique=True)
    description = models.CharField(max_length=200, blank=True)
    is_featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.name)
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class TroubleshootingEntry(models.Model):
    PRIORITY_CHOICES = [
        ("LOW", "Low"),
        ("MEDIUM", "Medium"),
        ("HIGH", "High"),
        ("CRITICAL", "Critical"),
    ]

    STATUS_CHOICES = [
        ("DRAFT", "Draft"),
        ("PUBLISHED", "Published"),
        ("ARCHIVED", "Archived"),
        ("PENDING_REVIEW", "Pending Review"),
    ]

    # Basic Information
    title = models.CharField(max_length=200)
    slug = models.SlugField(max_length=220, unique=True)
    problem_description = models.TextField()
    solution = models.TextField()

    # Additional Details
    steps_to_reproduce = models.TextField(
        blank=True, help_text="Step-by-step instructions to reproduce the problem"
    )
    environment_details = models.TextField(
        blank=True, help_text="OS, software versions, hardware specs, etc."
    )
    error_messages = models.TextField(
        blank=True, help_text="Exact error messages encountered"
    )
    prerequisites = models.TextField(
        blank=True, help_text="What needs to be done before applying this solution"
    )
    estimated_time = models.PositiveIntegerField(
        null=True, blank=True, help_text="Estimated time to resolve in minutes"
    )

    # Categorization
    category = models.ForeignKey(
        Category, on_delete=models.CASCADE, related_name="entries"
    )
    tags = models.ManyToManyField(Tag, blank=True, related_name="entries")

    # Metadata
    author = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="authored_entries"
    )
    priority = models.CharField(
        max_length=10, choices=PRIORITY_CHOICES, default="MEDIUM"
    )
    status = models.CharField(
        max_length=15, choices=STATUS_CHOICES, default="PUBLISHED"
    )

    # Verification System
    is_verified = models.BooleanField(default=False)
    verified_by = models.ForeignKey(
        User,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="verified_entries",
    )
    verified_at = models.DateTimeField(null=True, blank=True)
    verification_notes = models.TextField(blank=True)

    # Statistics
    upvotes_count = models.PositiveIntegerField(default=0)
    # downvotes_count = models.PositiveIntegerField(default=0)

    # Timestamps
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # search vector
    search_vector = SearchVectorField(null=True, blank=True, editable=False)

    class Meta:
        ordering = ["-created_at"]
        indexes = [
            GinIndex(fields=["search_vector"]),
            models.Index(fields=["category", "-created_at"]),
            models.Index(fields=["author", "-created_at"]),
            models.Index(fields=["-upvotes_count"]),
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["is_verified", "status"]),
        ]

    def save(self, *args, **kwargs):
        if not self.slug:
            self.slug = slugify(self.title)

        # Update the search vector
        """
        Check later when using pg
        """
        # self.search_vector = (
        #     SearchVector('title', weight='A') +
        #     SearchVector('problem_description', weight='B') +
        #     SearchVector('solution', weight='B') +
        #     SearchVector('tags__name', weight='C') # You can even include related fields
        # )
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title


class EntryRevision(models.Model):
    """Track changes to troubleshooting entries"""

    entry = models.ForeignKey(
        TroubleshootingEntry, on_delete=models.CASCADE, related_name="revisions"
    )
    revised_by = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=200)
    problem_description = models.TextField()
    solution = models.TextField()
    change_summary = models.CharField(max_length=200, blank=True)
    revision_number = models.PositiveIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ["entry", "revision_number"]
        ordering = ["-revision_number"]

    # Inside EntryRevision model
    def save(self, *args, **kwargs):
        if not self.pk:  # Only on creation
            latest_revision = (
                EntryRevision.objects.filter(entry=self.entry)
                .order_by("-revision_number")
                .first()
            )
            if latest_revision:
                self.revision_number = latest_revision.revision_number + 1
            else:
                self.revision_number = 1
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Revision {self.revision_number} for {self.entry.title} by {self.revised_by.username}"


class Attachment(models.Model):
    ATTACHMENT_TYPES = [
        ("IMAGE", "Image"),
        ("DOCUMENT", "Document"),
        ("VIDEO", "Video"),
        ("AUDIO", "Audio"),
        ("ARCHIVE", "Archive"),
        ("OTHER", "Other"),
    ]

    troubleshooting_entry = models.ForeignKey(
        TroubleshootingEntry, on_delete=models.CASCADE, related_name="attachments"
    )
    file = models.FileField(
        upload_to="troubleshooting_attachments/%Y/%m/",
        validators=[
            FileExtensionValidator(
                allowed_extensions=[
                    "jpg",
                    "jpeg",
                    "png",
                    "gif",
                    "pdf",
                    "txt",
                    "doc",
                    "docx",
                    "xls",
                    "xlsx",
                    "mp4",
                    "avi",
                    "mov",
                    "mp3",
                    "wav",
                    "zip",
                    "rar",
                ]
            )
        ],
    )
    original_filename = models.CharField(max_length=255)
    file_type = models.CharField(max_length=10, choices=ATTACHMENT_TYPES)
    file_size = models.PositiveIntegerField()  # in bytes
    mime_type = models.CharField(max_length=100)
    description = models.CharField(max_length=200, blank=True)

    # Image-specific fields
    uploaded_by = models.ForeignKey(User, on_delete=models.CASCADE)
    uploaded_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["uploaded_at"]

    def save(self, *args, **kwargs):
        if self.file and not self.original_filename:
            self.original_filename = os.path.basename(self.file.name)
        if self.file and not self.file_size:
            self.file_size = self.file.size
        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.original_filename} ({self.troubleshooting_entry.title})"


class Vote(models.Model):
    VOTE_TYPES = [
        ("UP", "Upvote"),
        ("DOWN", "Downvote"),
    ]

    troubleshooting_entry = models.ForeignKey(
        TroubleshootingEntry, on_delete=models.CASCADE, related_name="votes"
    )
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    vote_type = models.CharField(max_length=4, choices=VOTE_TYPES)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        unique_together = ["troubleshooting_entry", "user"]
        indexes = [
            models.Index(fields=["troubleshooting_entry", "vote_type"]),
        ]

    def __str__(self):
        return f"{self.user.username} {self.vote_type}voted {self.troubleshooting_entry.title}"


class Comment(models.Model):
    troubleshooting_entry = models.ForeignKey(
        TroubleshootingEntry, on_delete=models.CASCADE, related_name="comments"
    )
    parent = models.ForeignKey(
        "self", null=True, blank=True, on_delete=models.CASCADE, related_name="replies"
    )
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    is_solution = models.BooleanField(
        default=False
    )  # Mark if this comment provides an alternative solution

    is_edited = models.BooleanField(default=False)
    is_deleted = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    # Hierarchy
    # path = models.CharField(max_length=255, unique=True)  # For ltree implementation
    # level = models.PositiveIntegerField(default=0)  # For depth tracking

    class Meta:
        ordering = ["created_at"]

    def __str__(self):
        return (
            f"Comment by {self.author.username} on {self.troubleshooting_entry.title}"
        )
