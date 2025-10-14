from rest_framework.routers import DefaultRouter
from django.urls import path, include
from .views import (
    CategoryViewSet,
    TagViewSet,
    TroubleshootingEntryViewSet)

router = DefaultRouter()

router.register(r"categories", CategoryViewSet)
router.register(r"tags", TagViewSet)
router.register("entries", TroubleshootingEntryViewSet, basename="troubleshootingentry")

urlpatterns = [
    path('', include(router.urls)),
]