from django.db.models import Count, Q, Prefetch
from django.contrib.auth import get_user_model
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from .models import Category, Tag, TroubleshootingEntry
from .serializers import (
    CategorySerializer,
    TagSerializer,
    TroubleshootingEntryListSerializer,
    TroubleshootingEntryDetailSerializer,
    TroubleshootingEntryCreateSerializer,
    TroubleshootingEntryVerificationSerializer,
)

User = get_user_model()


# ------------------------------------------------------------------
# ViewSets
# ------------------------------------------------------------------
class CategoryViewSet(ModelViewSet):
    """
    List / manage categories.
    Tree structure returned in full – client should cache.
    """
    serializer_class = CategorySerializer
    permission_classes = [AllowAny]
    queryset = Category.objects.filter(is_active=True)

    def get_queryset(self):
        # prefetch only active children so get_subcategories() is free
        return (
            super()
            .get_queryset()
            .prefetch_related(
                Prefetch(
                    "subcategories",
                    queryset=Category.objects.filter(is_active=True),
                )
            )
            .annotate(entry_count=Count("entries", filter=Q(entries__status="PUBLISHED")))
        )


class TagViewSet(ModelViewSet):
    """
    List / manage tags.
    """
    serializer_class = TagSerializer
    permission_classes = [AllowAny]
    queryset = Tag.objects.all()

    def get_queryset(self):
        return super().get_queryset().annotate(
            entry_count=Count("entries", filter=Q(entries__status="PUBLISHED"))
        )


class TroubleshootingEntryViewSet(ModelViewSet):
    """
    List, retrieve, create, update troubleshooting entries.

    **Additional endpoints**
    -------------
    `POST /entries/{id}/verify/` – staff verification (IsAdminUser)
    """

    permission_classes = [AllowAny]

    def get_queryset(self):
        """
        List endpoint is heavily optimised; detail falls back to same QS.
        """
        qs = (
            TroubleshootingEntry.objects.select_related(
                "category", "author", "verified_by"
            )
            .prefetch_related("tags")
            .annotate(
                score=Count("votes__id", filter=Q(votes__value=1))
                - Count("votes__id", filter=Q(votes__value=-1)),
                total_votes=Count("votes__id"),
            )
        )
        # hide drafts from anonymous users
        if self.request.user.is_anonymous:
            qs = qs.filter(status=TroubleshootingEntry.Status.PUBLISHED)
        return qs

    def get_serializer_class(self):
        if self.action == "list":
            return TroubleshootingEntryListSerializer
        if self.action == "create":
            return TroubleshootingEntryCreateSerializer
        if self.action == "verify":
            return TroubleshootingEntryVerificationSerializer
        return TroubleshootingEntryDetailSerializer

    def get_permissions(self):
        """
        Create / update / verify require authenticated or staff.
        """
        if self.action in ("create", "update", "partial_update", "destroy"):
            return [IsAuthenticated()]
        if self.action == "verify":
            return [IsAdminUser()]
        return super().get_permissions()

    @action(detail=True, methods=["patch"])
    def verify(self, request, pk=None):
        """
        Staff verification action.
        Payload: {"is_verified": bool, "verification_notes": str}
        """
        entry = self.get_object()
        serializer = self.get_serializer(entry, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)