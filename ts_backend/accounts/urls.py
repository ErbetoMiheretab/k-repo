from django.urls import path, include
from rest_framework.routers import DefaultRouter

from . import views
# from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView



router = DefaultRouter()
router.register(r'departments', views.DepartmentViewSet, basename='department')
router.register(r'users', views.UserViewSet, basename='user')

urlpatterns = [
    path('', include(router.urls)),

    #Auth endpoints
    path('token/', views.CustomTokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', views.TokenRefreshView.as_view(), name='token_refresh'),

    # User profile endpoints
    path('profile/', views.UserProfileView.as_view(), name='user_profile'),
    path('change-password/', views.ChangePasswordView.as_view(), name='change_password'),
    
    # Department managemnt
    path('my-department-members/', views.MyDepartmentMembersView.as_view(), name='my_department_members'),

]