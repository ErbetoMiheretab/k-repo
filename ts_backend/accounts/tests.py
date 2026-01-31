from django.test import TestCase
from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from rest_framework.test import APIClient, APITestCase
from rest_framework import status
from .models import Department

User = get_user_model()


class ModelTests(TestCase):
    def setUp(self):
        self.department = Department.objects.create(name='CYBER_SECURITY', description='Cyber Security Department')
        self.user = User.objects.create_user(
            username='testuser',
            password='password123',
            email='test@example.com',
            user_type='TECH',
            role='CYBER_SECURITY',
            department=self.department
        )
        self.team_leader = User.objects.create_user(
            username='leader',
            password='password123',
            email='leader@example.com',
            user_type='SENIOR_TECH',
            role='CYBER_SECURITY',
            department=self.department
        )

    def test_department_creation(self):
        self.assertEqual(self.department.name, 'CYBER_SECURITY')
        self.assertEqual(str(self.department), 'Cyber Security')
        self.assertEqual(self.department.get_member_count(), 2)

    def test_user_creation(self):
        self.assertEqual(self.user.username, 'testuser')
        self.assertTrue(self.user.check_password('password123'))
        self.assertEqual(self.user.department, self.department)
        self.assertEqual(self.user.full_name, '')
        self.user.first_name = "Test"
        self.user.last_name = "User"
        self.user.save()
        self.assertEqual(self.user.full_name, 'Test User')

    def test_user_save_admin(self):
        admin_user = User.objects.create_user(
            username='adminuser',
            password='password123',
            email='admin@example.com',  # Added required email
            user_type='ADMIN'
        )
        self.assertTrue(admin_user.is_superuser)
        self.assertTrue(admin_user.is_staff)

    def test_team_leader_validation(self):
        # Create a department and try to assign a user who is not in that department
        other_dept = Department.objects.create(name='NETWORK', description='Network Department')
        
        # Try to assign team leader who is not in the department
        other_dept.team_leader = self.user  # self.user is in self.department, not other_dept
        
        with self.assertRaises(ValidationError):
            other_dept.full_clean()  # This will trigger the validation error

    def test_unique_email_validation(self):
        with self.assertRaises(ValidationError):
            user2 = User(username='testuser2', email='test@example.com')
            user2.full_clean()


class APIV1Tests(APITestCase):
    def setUp(self):
        # Departments
        self.department1 = Department.objects.create(name='CYBER_SECURITY', description='Cyber Security Department')
        self.department2 = Department.objects.create(name='NETWORK', description='Network Department')

        # Users
        self.admin_user = User.objects.create_superuser('admin', 'admin@example.com', 'password123', user_type='ADMIN')
        self.senior_tech = User.objects.create_user(
            'senior_tech', 'senior@example.com', 'password123',
            user_type='SENIOR_TECH', role='CYBER_SECURITY', department=self.department1,
            first_name='Senior', last_name='Tech'
        )
        self.tech_user = User.objects.create_user(
            'tech_user', 'tech@example.com', 'password123',
            user_type='TECH', role='CYBER_SECURITY', department=self.department1,
            is_verified=True
        )
        self.viewer_user = User.objects.create_user('viewer', 'viewer@example.com', 'password123', user_type='VIEWER')

        # Assign team leader
        self.department1.team_leader = self.senior_tech
        self.department1.save()
        
        self.client = APIClient()

    def _login(self, user, password='password123'):
        self.client.login(username=user.username, password=password)
        return self

    def test_unauthenticated_access(self):
        response = self.client.get('/api/v1/accounts/users/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        response = self.client.get('/api/v1/accounts/departments/')
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_get_user_list_as_admin(self):
        self._login(self.admin_user)
        response = self.client.get('/api/v1/accounts/users/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 4)

    def test_get_user_list_as_non_admin(self):
        self._login(self.tech_user)
        response = self.client.get('/api/v1/accounts/users/')
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_me_endpoint(self):
        self._login(self.tech_user)
        response = self.client.get('/api/v1/accounts/users/me/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['username'], self.tech_user.username)

    def test_department_list(self):
        self._login(self.tech_user)
        response = self.client.get('/api/v1/accounts/departments/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['results']), 2)

    def test_department_creation_as_admin(self):
        self._login(self.admin_user)
        data = {'name': 'DATABASE_AND_SOFTWARE_DEV', 'description': 'DB and Dev'}
        response = self.client.post('/api/v1/accounts/departments/', data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

    def test_department_creation_as_non_admin(self):
        self._login(self.tech_user)
        data = {'name': 'DATABASE_AND_SOFTWARE_DEV', 'description': 'DB and Dev'}
        response = self.client.post('/api/v1/accounts/departments/', data)
        # IsTeamLeaderOrReadOnly permission allows read-only access for non-admins
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_department_update_as_team_leader(self):
        self._login(self.senior_tech)
        data = {'description': 'Updated description'}
        response = self.client.patch(f'/api/v1/accounts/departments/{self.department1.id}/', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.department1.refresh_from_db()
        self.assertEqual(self.department1.description, 'Updated description')

    def test_department_update_as_wrong_team_leader(self):
        self._login(self.senior_tech)
        data = {'description': 'Updated description'}
        response = self.client.patch(f'/api/v1/accounts/departments/{self.department2.id}/', data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_verify_user_as_admin(self):
        self._login(self.admin_user)
        response = self.client.post(f'/api/v1/accounts/users/{self.viewer_user.id}/verify/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.viewer_user.refresh_from_db()
        self.assertTrue(self.viewer_user.is_verified)

    def test_change_password(self):
        self._login(self.tech_user)
        data = {
            'old_password': 'password123',
            'new_password': 'newpassword123',
            'confirm_new_password': 'newpassword123'
        }
        response = self.client.post('/api/v1/accounts/change-password/', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.tech_user.refresh_from_db()
        self.assertTrue(self.tech_user.check_password('newpassword123'))

    def test_change_password_wrong_old(self):
        self._login(self.tech_user)
        data = {
            'old_password': 'wrongpassword',
            'new_password': 'newpassword123',
            'confirm_new_password': 'newpassword123'
        }
        response = self.client.post('/api/v1/accounts/change-password/', data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_my_department_members_as_team_leader(self):
        self._login(self.senior_tech)
        response = self.client.get('/api/v1/accounts/my-department-members/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['members']), 2) # senior_tech and tech_user

    def test_my_department_members_as_admin(self):
        self._login(self.admin_user)
        response = self.client.get('/api/v1/accounts/my-department-members/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['members']), 4)

    def test_token_obtain(self):
        data = {'username': 'tech_user', 'password': 'password123'}
        response = self.client.post('/api/v1/accounts/token/', data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('access', response.data)
        self.assertIn('refresh', response.data)
        self.assertEqual(response.data['user_type'], 'TECH')

    def test_department_members_endpoint(self):
        self._login(self.admin_user)
        response = self.client.get(f'/api/v1/accounts/departments/{self.department1.id}/members/')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Check if response is paginated or not
        if 'results' in response.data:
            self.assertEqual(len(response.data['results']), 2)
        else:
            self.assertEqual(len(response.data), 2)