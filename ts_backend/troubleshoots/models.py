from django.db import models, transaction
from django.contrib.auth import get_user_model
from django.db.models import Q, Count
from django.core.exceptions import ValidationError
from django.contrib.postgres.search import SearchVectorField
from django.contrib.postgres.indexes import GinIndex
from django.utils.text import slugify
from django.conf import settings
import re


User = get_user_model()





class SlugGenerationMixin(models.Model):
    """
    Mixin that automatically generates a unique slug from a
    char field called 'name' or 'title' (or supply your own field).
    The slug is only generated once – when the record is created –
    unless you pass `force_regenerate=True` to save().
    """

    SLUG_SEPARATOR = getattr(settings, "SLUG_SEPARATOR", "-")
    MAX_ITERATIONS = 1_000

    class Meta:
        abstract = True

    def generate_unique_slug(self, slug_source_field: str = "name") -> str:
        """
        Return a slug that is unique for this model.
        Uses a single query to fetch all existing candidates and works
        in-memory to avoid N+1 queries.
        """
        source = getattr(self, slug_source_field, None)
        if not source:
            raise ValueError(
                f"Cannot generate slug: {slug_source_field} field is empty"
            )

        base = slugify(source) or "untitled"
        slug_field = self._meta.get_field("slug")
        max_length = slug_field.max_length

        # pre-fetch all slugs that could collide
        pattern = rf"^{re.escape(base)}({re.escape(self.SLUG_SEPARATOR)}\d+)?$"
        existing = set(
            self.__class__.objects.filter(
                models.Q(slug__regex=pattern),
            )
            .exclude(pk=self.pk if not self._state.adding else None)
            .values_list("slug", flat=True)
        )

        # first candidate
        if base not in existing:
            return base[:max_length]

        # counter candidates
        counter = 2
        while counter <= self.MAX_ITERATIONS:
            candidate = f"{base}{self.SLUG_SEPARATOR}{counter}"
            if candidate not in existing:
                return candidate[:max_length]
            counter += 1

        raise ValueError(
            f"Could not produce a unique slug for '{source}' "
            f"after {self.MAX_ITERATIONS} attempts"
        )

    def save(self, *args, force_regenerate=False, **kwargs):
        if not hasattr(self, "slug"):
            raise AttributeError(
                f"{self.__class__.__name__} must contain a 'slug' field "
                "when using SlugGenerationMixin."
            )

        if not self.slug or force_regenerate:
            if hasattr(self, "title"):
                source_field = "title"
            elif hasattr(self, "name"):
                source_field = "name"
            else:
                raise AttributeError(
                    f"{self.__class__.__name__} needs either 'title' or 'name' "
                    "to auto-generate a slug."
                )

            # regenerate until we win the race-free lottery
            for attempt in range(10):  # 10 retries is plenty
                with transaction.atomic():
                    self.slug = self.generate_unique_slug(source_field)[: self._meta.get_field("slug").max_length]
                    try:
                        super().save(*args, **kwargs)
                        return  # success
                    except models.IntegrityError:  # slug collision
                        if attempt == 9:
                            raise
                        continue
        else:
            super().save(*args, **kwargs)
    
class Category(SlugGenerationMixin,models.Model):
    name = models.CharField(max_length=100, unique=True)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.TextField(blank=True)
    parent = models.ForeignKey(
        "self",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="subcategories",
    )
    is_active = models.BooleanField(default=True)
    order = models.PositiveIntegerField(default=0)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name_plural = "Categories"
        ordering = ["order", "name"]
    
    def clean(self):
        """Validate that a category cannot be its own parent"""
        if self.parent and self.parent == self:
            raise ValidationError("A category cannot be its own parent.")
        
        # Check for circular parent relationships
        if self.parent and self.parent_id:
            current = self.parent
            while current and current.parent:
                if current.parent_id == self.pk:
                    raise ValidationError("Circular parent relationship detected.")
                current = current.parent
        
    def __str__(self):
        return self.name


class Tag(SlugGenerationMixin, models.Model):
    name = models.CharField(max_length=220, unique=True)
    slug = models.SlugField(max_length=220, unique=True, blank=True)
    description = models.CharField(max_length=200, blank=True)
    is_featured = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]    

    def __str__(self):
        return self.name

class TroubleshootingEntryQuerySet(models.QuerySet):
    def with_related(self):
        return self.select_related(
            'category', 'author', 'verified_by'
        ).prefetch_related(
            'tags', 'attachments', 'votes'
        )


    def with_vote_score(self):                       
        return self.annotate(
            up_count=Count('votes', filter=Q(votes__vote_type='UP')),
            down_count=Count('votes', filter=Q(votes__vote_type='DOWN'))
        ).annotate(
            score=models.F('up_count') - models.F('down_count')
        )
    
class TroubleshootingEntry(SlugGenerationMixin,models.Model):
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
    slug = models.SlugField(max_length=220, unique=True, blank=True)
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
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["is_verified", "status"]),
        ]
        constraints = [
            # Ensure verified entries have verification details
            models.CheckConstraint(
                check=Q(is_verified=False) | (Q(verified_by__isnull=False) & Q(verified_at__isnull=False)),
                name='verified_entries_must_have_verifier'
            ),
            # Ensure estimated time is reasonable
            models.CheckConstraint(
                check=Q(estimated_time__isnull=True) | Q(estimated_time__lte=10080),  # 1 week max
                name='reasonable_estimated_time'
            ),
        ]
    
    @property
    def total_votes(self):
        return self.votes.count()

    @property
    def vote_score(self):
        return self.votes.filter(vote_type='UP').count() - self.votes.filter(vote_type='DOWN').count()

    def get_absolute_url(self):
        from django.urls import reverse
        return reverse('entry-detail', kwargs={'slug': self.slug})


    #def save(self, *args, **kwargs):

        # Update the search vector
        
        #Check later when using pg
        
        # self.search_vector = (
        #     SearchVector('title', weight='A') +
        #     SearchVector('problem_description', weight='B') +
        #     SearchVector('solution', weight='B') +
        #     SearchVector('tags__name', weight='C') # You can even include related fields
        # )
        #super().save(*args, **kwargs)
    def clean(self):
        """Custom validation"""
        if self.is_verified and not self.verified_by:
            raise ValidationError({
                'verified_by': 'Verified entries must have a verifier.'
            })
        
        if self.is_verified and not self.verified_at:
            raise ValidationError({
                'verified_at': 'Verified entries must have a verification timestamp.'
            })

    def save(self, *args, **kwargs):
        # Auto-set verified_at if being verified
        if self.is_verified and not self.verified_at:
            from django.utils import timezone
            self.verified_at = timezone.now()
            
        super().save(*args, **kwargs)

    def __str__(self):
        return self.title

    objects = TroubleshootingEntryQuerySet.as_manager()

