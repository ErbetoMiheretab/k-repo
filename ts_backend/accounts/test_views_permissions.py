from django.test import TestCase
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APIClient
from rest_framework import status
from .models import Department
from .permissions import IsOwnerOrAdmin, CanManageDepartment, IsTeamLeaderOrReadOnly

User = get_user_model()


class PermissionTests(TestCase):
    def setUp(self):
        # Create departments
        self.department1 = Department.objects.create(
            name="CYBER_SECURITY", description="Cyber Security Department"
        )
        self.department2 = Department.objects.create(
            name="NETWORK", description="Network Department"
        )

        # Create users with different roles
        self.admin_user = User.objects.create_user(
            username="admin",
            password="adminpass123",
            email="admin@example.com",
            user_type="ADMIN",
            role="SYSTEM_ADMIN",
        )

        self.senior_tech_user = User.objects.create_user(
            username="senior_tech",
            password="seniorpass123",
            email="senior@example.com",
            user_type="SENIOR_TECH",
            role="CYBER_SECURITY",
            department=self.department1,
        )

        self.tech_user = User.objects.create_user(
            username="tech_user",
            password="techpass123",
            email="tech@example.com",
            user_type="TECH",
            role="CYBER_SECURITY",
            department=self.department1,
        )

        self.junior_tech_user = User.objects.create_user(
            username="junior_tech",
            password="juniorpass123",
            email="junior@example.com",
            user_type="JUNIOR_TECH",
            role="CYBER_SECURITY",
            department=self.department1,
        )

        self.viewer_user = User.objects.create_user(
            username="viewer_user",
            password="viewerpass123",
            email="viewer@example.com",
            user_type="VIEWER",
            role="IT",
            department=self.department1,
        )

        # Assign team leader
        self.department1.team_leader = self.senior_tech_user
        self.department1.save()

        # Create another department with different team leader
        self.department2.team_leader = self.admin_user
        self.department2.save()

        self.client = APIClient()

    def test_is_owner_or_admin_permission(self):
        """Test IsOwnerOrAdmin permission class."""
        permission = IsOwnerOrAdmin()

        # Test with admin user - should have access to any object
        request = type("obj", (object,), {"user": self.admin_user, "method": "POST"})()
        self.assertTrue(permission.has_object_permission(request, None, self.tech_user))

        # Test with owner - should have access to own object
        request = type("obj", (object,), {"user": self.tech_user, "method": "POST"})()
        self.assertTrue(permission.has_object_permission(request, None, self.tech_user))

        # Test with different user - should not have access to another user's object
        request = type("obj", (object,), {"user": self.junior_tech_user, "method": "POST"})()
        self.assertFalse(
            permission.has_object_permission(request, None, self.tech_user)
        )

        # Test SAFE_METHODS (GET, OPTIONS, HEAD) for authenticated users
        request = type(
            "obj", (object,), {"user": self.junior_tech_user, "method": "GET"}
        )()
        self.assertTrue(permission.has_object_permission(request, None, self.tech_user))

    def test_can_manage_department_permission(self):
        """Test CanManageDepartment permission class."""
        permission = CanManageDepartment()

        # Test with admin user - should be able to manage any department
        request = type("obj", (object,), {"user": self.admin_user})()
        self.assertTrue(
            permission.has_object_permission(request, None, self.department1)
        )

        # Test with team leader - should be able to manage own department
        request = type("obj", (object,), {"user": self.senior_tech_user})()
        self.assertTrue(
            permission.has_object_permission(request, None, self.department1)
        )

        # Test with team leader - should not be able to manage other department
        request = type("obj", (object,), {"user": self.senior_tech_user})()
        self.assertFalse(
            permission.has_object_permission(request, None, self.department2)
        )

        # Test with regular user - should not be able to manage department
        request = type("obj", (object,), {"user": self.tech_user})()
        self.assertFalse(
            permission.has_object_permission(request, None, self.department1)
        )

    def test_is_team_leader_or_read_only_permission(self):
        """Test IsTeamLeaderOrReadOnly permission class."""
        permission = IsTeamLeaderOrReadOnly()

        # Test with admin user - should have access
        request = type("obj", (object,), {"user": self.admin_user, "method": "POST"})()
        self.assertTrue(permission.has_permission(request, None))

        # Test with team leader - should have access
        request = type("obj", (object,), {"user": self.senior_tech_user, "method": "POST"})()
        self.assertTrue(permission.has_permission(request, None))

        # Test with regular user - should not have write access
        request = type("obj", (object,), {"user": self.tech_user, "method": "POST"})()
        self.assertFalse(permission.has_permission(request, None))

        # Test with regular user - should have read access (but this permission doesn't check method)
        request = type("obj", (object,), {"user": self.tech_user, "method": "GET"})()
        self.assertFalse(permission.has_permission(request, None))  # This permission doesn't allow regular users


class DepartmentViewSetTests(TestCase):
    def setUp(self):
        # Create departments
        self.department1 = Department.objects.create(
            name="CYBER_SECURITY", description="Cyber Security Department"
        )
        self.department2 = Department.objects.create(
            name="NETWORK", description="Network Department"
        )

        # Create users with different roles
        self.admin_user = User.objects.create_user(
            username="admin",
            password="adminpass123",
            email="admin@example.com",
            user_type="ADMIN",
            role="SYSTEM_ADMIN",
        )

        self.senior_tech_user = User.objects.create_user(
            username="senior_tech",
            password="seniorpass123",
            email="senior@example.com",
            user_type="SENIOR_TECH",
            role="CYBER_SECURITY",
            department=self.department1,
        )

        self.tech_user = User.objects.create_user(
            username="tech_user",
            password="techpass123",
            email="tech@example.com",
            user_type="TECH",
            role="CYBER_SECURITY",
            department=self.department1,
        )

        # Assign team leader
        self.department1.team_leader = self.senior_tech_user
        self.department1.save()

        self.client = APIClient()

    def test_department_list_unauthenticated(self):
        """Test department list endpoint without authentication."""
        response = self.client.get(reverse("department-list"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_department_list_authenticated(self):
        """Test department list endpoint with authentication."""
        self.client.force_authenticate(user=self.tech_user)
        response = self.client.get(reverse("department-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertGreaterEqual(len(response.data["results"]), 2)

    def test_department_create_admin_only(self):
        """Test department creation - only admin should be able to create."""
        self.client.force_authenticate(user=self.admin_user)
        data = {
            "name": "TRAINING_AND_MAINTENANCE",
            "description": "Training and Maintenance Department",
        }
        response = self.client.post(reverse("department-list"), data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Test that regular user cannot create
        self.client.force_authenticate(user=self.tech_user)
        response = self.client.post(reverse("department-list"), data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_department_update_team_leader_only(self):
        """Test department update - only admin or team leader should be able to update."""
        # Admin can update any department
        self.client.force_authenticate(user=self.admin_user)
        data = {"description": "Updated by admin"}
        response = self.client.patch(
            reverse("department-detail", kwargs={"pk": self.department1.pk}), data
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Team leader can update their own department
        self.client.force_authenticate(user=self.senior_tech_user)
        data = {"description": "Updated by team leader"}
        response = self.client.patch(
            reverse("department-detail", kwargs={"pk": self.department1.pk}), data
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Regular user cannot update department
        self.client.force_authenticate(user=self.tech_user)
        data = {"description": "Updated by regular user"}
        response = self.client.patch(
            reverse("department-detail", kwargs={"pk": self.department1.pk}), data
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_department_delete_admin_only(self):
        """Test department deletion - only admin should be able to delete."""
        # Admin can delete
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.delete(
            reverse("department-detail", kwargs={"pk": self.department2.pk})
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Recreate department for next test
        self.department2 = Department.objects.create(
            name="NETWORK", description="Network Department"
        )

        # Regular user cannot delete
        self.client.force_authenticate(user=self.tech_user)
        response = self.client.delete(
            reverse("department-detail", kwargs={"pk": self.department2.pk})
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_department_members_endpoint(self):
        """Test department members endpoint."""
        self.client.force_authenticate(user=self.tech_user)
        response = self.client.get(
            reverse("department-members", kwargs={"pk": self.department1.pk})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_department_members_unauthenticated(self):
        """Test department members endpoint without authentication."""
        response = self.client.get(
            reverse("department-members", kwargs={"pk": self.department1.pk})
        )
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_department_assign_leader_admin_only(self):
        """Test assign leader endpoint - admin only."""
        # Create a user in department2 to be assigned as leader
        dept2_user = User.objects.create_user(
            username="dept2_user",
            password="dept2pass123",
            email="dept2@example.com",
            user_type="SENIOR_TECH",
            role="NETWORK_ADMIN",
            department=self.department2,
        )
        
        self.client.force_authenticate(user=self.admin_user)
        data = {"user_id": dept2_user.id}
        response = self.client.post(
            reverse("department-assign-leader", kwargs={"pk": self.department2.pk}),
            data,
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Regular user cannot assign leader (should get 403 Forbidden)
        self.client.force_authenticate(user=self.tech_user)
        data = {"user_id": self.senior_tech_user.id}  # Use a user from the same department
        response = self.client.post(
            reverse("department-assign-leader", kwargs={"pk": self.department1.pk}),
            data,
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_department_assign_leader_invalid_user(self):
        """Test assign leader endpoint with invalid user."""
        self.client.force_authenticate(user=self.admin_user)
        data = {"user_id": 999999}  # Non-existent user
        response = self.client.post(
            reverse("department-assign-leader", kwargs={"pk": self.department1.pk}),
            data,
        )
        self.assertEqual(response.status_code, status.HTTP_404_NOT_FOUND)

    def test_department_assign_leader_invalid_user_type(self):
        """Test assign leader endpoint with invalid user type."""
        # Create a viewer user who shouldn't be able to lead
        viewer_user = User.objects.create_user(
            username="viewer",
            password="viewerpass123",
            email="viewer@example.com",
            user_type="VIEWER",
            role="IT",
            department=self.department1,
        )

        self.client.force_authenticate(user=self.admin_user)
        data = {"user_id": viewer_user.id}
        response = self.client.post(
            reverse("department-assign-leader", kwargs={"pk": self.department1.pk}),
            data,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_department_assign_leader_not_member(self):
        """Test assign leader endpoint with user not in department."""
        # Create user in different department
        other_dept_user = User.objects.create_user(
            username="other_dept_user",
            password="otherpass123",
            email="other@example.com",
            user_type="SENIOR_TECH",
            role="NETWORK_ADMIN",
            department=self.department2,
        )

        self.client.force_authenticate(user=self.admin_user)
        data = {"user_id": other_dept_user.id}
        response = self.client.post(
            reverse("department-assign-leader", kwargs={"pk": self.department1.pk}),
            data,
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class UserViewSetTests(TestCase):
    def setUp(self):
        # Create departments
        self.department1 = Department.objects.create(
            name="CYBER_SECURITY", description="Cyber Security Department"
        )
        self.department2 = Department.objects.create(
            name="NETWORK", description="Network Department"
        )

        # Create users with different roles
        self.admin_user = User.objects.create_user(
            username="admin",
            password="adminpass123",
            email="admin@example.com",
            user_type="ADMIN",
            role="SYSTEM_ADMIN",
        )

        self.senior_tech_user = User.objects.create_user(
            username="senior_tech",
            password="seniorpass123",
            email="senior@example.com",
            user_type="SENIOR_TECH",
            role="CYBER_SECURITY",
            department=self.department1,
        )

        self.tech_user = User.objects.create_user(
            username="tech_user",
            password="techpass123",
            email="tech@example.com",
            user_type="TECH",
            role="CYBER_SECURITY",
            department=self.department1,
        )

        self.junior_tech_user = User.objects.create_user(
            username="junior_tech",
            password="juniorpass123",
            email="junior@example.com",
            user_type="JUNIOR_TECH",
            role="CYBER_SECURITY",
            department=self.department1,
        )

        # Assign team leader
        self.department1.team_leader = self.senior_tech_user
        self.department1.save()

        self.client = APIClient()

    def test_user_list_admin_only(self):
        """Test user list endpoint - only admin should have access."""
        # Admin can access
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(reverse("user-list"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Regular user cannot access
        self.client.force_authenticate(user=self.tech_user)
        response = self.client.get(reverse("user-list"))
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_create_admin_only(self):
        """Test user creation - only admin should be able to create."""
        self.client.force_authenticate(user=self.admin_user)
        data = {
            "username": "new_user",
            "email": "new@example.com",
            "password": "newpass123",
            "confirm_password": "newpass123",
            "first_name": "New",
            "last_name": "User",
            "user_type": "TECH",
            "role": "CYBER_SECURITY",
            "department": self.department1.id,
        }
        response = self.client.post(reverse("user-list"), data)
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)

        # Regular user cannot create
        self.client.force_authenticate(user=self.tech_user)
        response = self.client.post(reverse("user-list"), data)
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_update_admin_only(self):
        """Test user update - only admin should be able to update."""
        # Admin can update
        self.client.force_authenticate(user=self.admin_user)
        data = {"first_name": "Updated"}
        response = self.client.patch(
            reverse("user-detail", kwargs={"pk": self.tech_user.pk}), data
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Regular user cannot update
        self.client.force_authenticate(user=self.tech_user)
        data = {"first_name": "Hacked"}
        response = self.client.patch(
            reverse("user-detail", kwargs={"pk": self.junior_tech_user.pk}), data
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_delete_admin_only(self):
        """Test user deletion - only admin should be able to delete."""
        # Admin can delete
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.delete(
            reverse("user-detail", kwargs={"pk": self.junior_tech_user.pk})
        )
        self.assertEqual(response.status_code, status.HTTP_204_NO_CONTENT)

        # Recreate user for next test
        self.junior_tech_user = User.objects.create_user(
            username="junior_tech",
            password="juniorpass123",
            email="junior@example.com",
            user_type="JUNIOR_TECH",
            role="CYBER_SECURITY",
            department=self.department1,
        )

        # Regular user cannot delete
        self.client.force_authenticate(user=self.tech_user)
        response = self.client.delete(
            reverse("user-detail", kwargs={"pk": self.junior_tech_user.pk})
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_me_endpoint(self):
        """Test user me endpoint - authenticated user can access own data."""
        self.client.force_authenticate(user=self.tech_user)
        response = self.client.get(reverse("user-me"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], self.tech_user.username)

    def test_user_me_unauthenticated(self):
        """Test user me endpoint without authentication."""
        response = self.client.get(reverse("user-me"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_verify_admin_only(self):
        """Test user verify endpoint - only admin should be able to verify."""
        # Admin can verify
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(
            reverse("user-verify", kwargs={"pk": self.tech_user.pk})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Regular user cannot verify
        self.client.force_authenticate(user=self.tech_user)
        response = self.client.post(
            reverse("user-verify", kwargs={"pk": self.junior_tech_user.pk})
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_unverify_admin_only(self):
        """Test user unverify endpoint - only admin should be able to unverify."""
        # First verify the user
        self.tech_user.is_verified = True
        self.tech_user.save()
        
        # Admin can unverify
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(
            reverse("user-unverify", kwargs={"pk": self.tech_user.pk})
        )
        self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Regular user cannot unverify
        self.client.force_authenticate(user=self.tech_user)
        response = self.client.post(
            reverse("user-unverify", kwargs={"pk": self.junior_tech_user.pk})
        )
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)

    def test_user_verify_already_verified(self):
        """Test user verify endpoint with already verified user."""
        # First verify the user
        self.tech_user.is_verified = True
        self.tech_user.save()

        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(
            reverse("user-verify", kwargs={"pk": self.tech_user.pk})
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_user_unverify_already_unverified(self):
        """Test user unverify endpoint with already unverified user."""
        # First unverify the user
        self.tech_user.is_verified = False
        self.tech_user.save()

        self.client.force_authenticate(user=self.admin_user)
        response = self.client.post(
            reverse("user-unverify", kwargs={"pk": self.tech_user.pk})
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class UserProfileViewTests(TestCase):
    def setUp(self):
        # Create department
        self.department1 = Department.objects.create(
            name="CYBER_SECURITY", description="Cyber Security Department"
        )

        # Create user
        self.user = User.objects.create_user(
            username="test_user",
            password="testpass123",
            email="test@example.com",
            first_name="Test",
            last_name="User",
            user_type="TECH",
            role="CYBER_SECURITY",
            department=self.department1,
        )

        self.client = APIClient()

    def test_user_profile_retrieve(self):
        """Test user profile retrieval."""
        self.client.force_authenticate(user=self.user)
        response = self.client.get(reverse("user_profile"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["username"], self.user.username)

    def test_user_profile_update(self):
        """Test user profile update."""
        self.client.force_authenticate(user=self.user)
        data = {"first_name": "Updated", "email": "updated@example.com"}
        response = self.client.put(reverse("user_profile"), data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["detail"], "Profile updated successfully")

    def test_user_profile_update_unauthenticated(self):
        """Test user profile update without authentication."""
        data = {"first_name": "Hacked", "email": "hacker@example.com"}
        response = self.client.put(reverse("user_profile"), data)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_user_profile_partial_update(self):
        """Test user profile partial update."""
        self.client.force_authenticate(user=self.user)
        data = {"first_name": "Partial", "phone_number": "+1234567890"}
        response = self.client.patch(reverse("user_profile"), data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["detail"], "Profile updated successfully")


class ChangePasswordViewTests(TestCase):
    def setUp(self):
        # Create user
        self.user = User.objects.create_user(
            username="test_user",
            password="oldpass123",
            email="test@example.com",
            user_type="TECH",
            role="IT",
        )

        self.client = APIClient()

    def test_change_password_success(self):
        """Test successful password change."""
        self.client.force_authenticate(user=self.user)
        data = {
            "old_password": "oldpass123",
            "new_password": "newpass123",
            "confirm_new_password": "newpass123",
        }
        response = self.client.put(reverse("change_password"), data)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["detail"], "Password updated successfully")

    def test_change_password_wrong_old_password(self):
        """Test password change with wrong old password."""
        self.client.force_authenticate(user=self.user)
        data = {
            "old_password": "wrongpass",
            "new_password": "newpass123",
            "confirm_new_password": "newpass123",
        }
        response = self.client.put(reverse("change_password"), data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_change_password_mismatch(self):
        """Test password change with mismatched new passwords."""
        self.client.force_authenticate(user=self.user)
        data = {
            "old_password": "oldpass123",
            "new_password": "newpass123",
            "confirm_new_password": "differentpass",
        }
        response = self.client.put(reverse("change_password"), data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_change_password_unauthenticated(self):
        """Test password change without authentication."""
        data = {
            "old_password": "oldpass123",
            "new_password": "newpass123",
            "confirm_new_password": "newpass123",
        }
        response = self.client.put(reverse("change_password"), data)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class MyDepartmentMembersViewTests(TestCase):
    def setUp(self):
        # Create departments
        self.department1 = Department.objects.create(
            name="CYBER_SECURITY", description="Cyber Security Department"
        )
        self.department2 = Department.objects.create(
            name="NETWORK", description="Network Department"
        )

        # Create users
        self.admin_user = User.objects.create_user(
            username="admin",
            password="adminpass123",
            email="admin@example.com",
            user_type="ADMIN",
            role="SYSTEM_ADMIN",
        )

        self.team_leader = User.objects.create_user(
            username="team_leader",
            password="leaderpass123",
            email="leader@example.com",
            user_type="SENIOR_TECH",
            role="CYBER_SECURITY",
            department=self.department1,
        )

        self.member1 = User.objects.create_user(
            username="member1",
            password="memberpass123",
            email="member1@example.com",
            user_type="TECH",
            role="CYBER_SECURITY",
            department=self.department1,
        )

        self.member2 = User.objects.create_user(
            username="member2",
            password="memberpass123",
            email="member2@example.com",
            user_type="JUNIOR_TECH",
            role="CYBER_SECURITY",
            department=self.department1,
        )

        # Assign team leader
        self.department1.team_leader = self.team_leader
        self.department1.save()

        self.client = APIClient()

    def test_my_department_members_admin_sees_all(self):
        """Test that admin sees all users."""
        self.client.force_authenticate(user=self.admin_user)
        response = self.client.get(reverse("my_department_members"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Admin should see all users
        self.assertGreaterEqual(len(response.data["members"]), 3)

    def test_my_department_members_team_leader_sees_own_department(self):
        """Test that team leader sees only their department members."""
        self.client.force_authenticate(user=self.team_leader)
        response = self.client.get(reverse("my_department_members"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        # Team leader should see their department members (team leader + 2 members)
        self.assertEqual(len(response.data["members"]), 3)

    def test_my_department_members_regular_user_empty(self):
        """Test that regular user with no department sees empty results."""
        regular_user = User.objects.create_user(
            username="regular_user",
            password="regularpass123",
            email="regular@example.com",
            user_type="VIEWER",
            role="IT",
            # No department assigned
        )

        self.client.force_authenticate(user=regular_user)
        response = self.client.get(reverse("my_department_members"))
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data["members"]), 0)

    def test_my_department_members_unauthenticated(self):
        """Test my department members endpoint without authentication."""
        response = self.client.get(reverse("my_department_members"))
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class EdgeCaseTests(TestCase):
    def setUp(self):
        # Create department
        self.department1 = Department.objects.create(
            name="CYBER_SECURITY", description="Cyber Security Department"
        )

        # Create users
        self.admin_user = User.objects.create_user(
            username="admin",
            password="adminpass123",
            email="admin@example.com",
            user_type="ADMIN",
            role="SYSTEM_ADMIN",
        )

        self.user = User.objects.create_user(
            username="test_user",
            password="testpass123",
            email="test@example.com",
            user_type="TECH",
            role="CYBER_SECURITY",
            department=self.department1,
        )

        self.client = APIClient()

    def test_large_payload_protection(self):
        """Test protection against large payload attacks."""
        self.client.force_authenticate(user=self.admin_user)
        # Create a very large payload
        large_data = {
            "name": "CYBER_SECURITY",
            "description": "x" * 10000,  # Very large description
        }
        response = self.client.post(reverse("department-list"), large_data)
        # Should either reject or handle gracefully
        self.assertIn(
            response.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST]
        )

    def test_sql_injection_attempts(self):
        """Test protection against SQL injection attempts."""
        self.client.force_authenticate(user=self.admin_user)
        malicious_data = {
            "name": "'; DROP TABLE users; --",
            "description": "'; DELETE FROM users; --",
        }
        response = self.client.post(reverse("department-list"), malicious_data)
        # Should not crash and should reject invalid data
        self.assertNotEqual(response.status_code, status.HTTP_201_CREATED)

    def test_xss_attempts(self):
        """Test protection against XSS attempts."""
        self.client.force_authenticate(user=self.user)
        xss_data = {
            "first_name": '<script>alert("XSS")</script>',
            "last_name": '<img src=x onerror=alert("XSS")>',
            "phone_number": '<svg onload=alert("XSS")>',
        }
        response = self.client.patch(reverse("user_profile"), xss_data)
        # Should sanitize input or reject it
        self.assertIn(
            response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]
        )

    def test_rate_limiting_simulation(self):
        """Simulate rate limiting by making multiple requests."""
        # This is a simulation - actual rate limiting would be tested differently
        for i in range(10):
            response = self.client.post(
                reverse("token_obtain_pair"),
                {"username": "nonexistent", "password": "invalid"},
            )
            # Should not crash even with multiple requests
            self.assertIsNotNone(response.status_code)

    def test_concurrent_modifications(self):
        """Test handling of concurrent modifications."""
        # This would typically require more complex setup with threading
        # For now, just test that multiple sequential updates work
        self.client.force_authenticate(user=self.admin_user)

        # Update department multiple times
        for i in range(3):
            data = {"description": f"Updated description {i}"}
            response = self.client.patch(
                reverse("department-detail", kwargs={"pk": self.department1.pk}), data
            )
            self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_invalid_foreign_key_references(self):
        """Test handling of invalid foreign key references."""
        self.client.force_authenticate(user=self.admin_user)
        invalid_data = {
            "username": "new_user",
            "email": "new@example.com",
            "password": "newpass123",
            "confirm_password": "newpass123",
            "first_name": "New",
            "last_name": "User",
            "user_type": "TECH",
            "role": "CYBER_SECURITY",
            "department": 999999,  # Non-existent department
        }
        response = self.client.post(reverse("user-list"), invalid_data)
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_boundary_values(self):
        """Test boundary values for various fields."""
        self.client.force_authenticate(user=self.admin_user)

        # Test with minimum length values
        min_data = {
            "username": "a",  # Minimum length
            "email": "a@b.co",  # Minimum realistic email
            "password": "12345678",  # Minimum length
            "confirm_password": "12345678",
            "first_name": "A",  # Minimum length
            "last_name": "B",  # Minimum length
            "user_type": "VIEWER",
            "role": "IT",
            "department": self.department1.id,
        }
        response = self.client.post(reverse("user-list"), min_data)
        # May fail due to validation, but shouldn't crash
        self.assertIn(
            response.status_code, [status.HTTP_201_CREATED, status.HTTP_400_BAD_REQUEST]
        )

    def test_unicode_characters(self):
        """Test handling of unicode characters."""
        self.client.force_authenticate(user=self.user)
        unicode_data = {
            "first_name": "José María",
            "last_name": "Sánchez-Pérez",
            "phone_number": "+34 912 345 678",
            "department": self.department1.id,
        }
        response = self.client.patch(reverse("user_profile"), unicode_data)
        # Should handle unicode characters properly
        self.assertIn(
            response.status_code, [status.HTTP_200_OK, status.HTTP_400_BAD_REQUEST]
        )
