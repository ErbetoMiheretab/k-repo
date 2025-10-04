import random
from django.core.management.base import BaseCommand
from django.contrib.auth import get_user_model
from django.db import transaction
from faker import Faker
from accounts.models import Department

User = get_user_model()
fake = Faker()


DEPARTMENT_CHOICES = [
    ('DATABASE_AND_SOFTWARE_DEV', 'Database and Software Development'),
    ('CYBER_SECURITY', 'Cyber Security'),
    ('NETWORK', 'Network'),
    ('TRAINING_AND_MAINTENANCE', 'Training and Maintenance'),
    ('DEPARTMENT', 'General Department'),
]

ROLE_POOL = [
    'IT', 'SYSTEM_ADMIN', 'SOFTWARE_MAINTENANCE', 'DATABASE_ADMIN',
    'CYBER_SECURITY', 'NETWORK_ADMIN', 'WEBSITE_ADMIN',
    'TECHNOLOGY_TRAINING_OFFICER', 'HARDWARE_MAINTENANCE', 'DATACENTER'
]

USER_TYPE_POOL = ['TECH', 'JUNIOR_TECH', 'SENIOR_TECH']


class Command(BaseCommand):
    help = 'Populate DB with fake departments, leaders, techs.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--flush',
            action='store_true',
            help='Delete all existing Department/User rows before seeding.',
        )

    @transaction.atomic
    def handle(self, *args, **options):
        if options['flush']:
            self.stdout.write(self.style.WARNING('Flushing existing data...'))
            User.objects.exclude(is_superuser=True).delete()
            Department.objects.all().delete()

        self.stdout.write('Creating departments...')
        departments = []
        for code, name in DEPARTMENT_CHOICES:
            d, _ = Department.objects.get_or_create(
                name=code,
                defaults={'description': fake.catch_phrase()}
            )
            departments.append(d)

        self.stdout.write('Creating super-user admin...')
        admin, _ = User.objects.get_or_create(
            username='admin',
            defaults={
                'email': 'admin@local.test',
                'first_name': 'Super',
                'last_name': 'Admin',
                'user_type': 'ADMIN',
                'is_superuser': True,
                'is_staff': True,
            }
        )
        if not admin.check_password('adm1nPass!'):
            admin.set_password('adm1nPass!')
            admin.save()

        for dept in departments:
            self.create_team_for(dept)

        self.stdout.write(self.style.SUCCESS('Fake data populated 🎉'))

    def create_team_for(self, dept):
        """Create 1 leader + 3-7 techs for a department."""
        leader = User.objects.create(
            username=fake.unique.user_name(),
            email=fake.unique.email(),
            first_name=fake.first_name(),
            last_name=fake.last_name(),
            user_type='SENIOR_TECH',
            role=random.choice(ROLE_POOL),
            department=dept,
            phone_number=fake.phone_number(),
        )
        leader.set_password('leadPass123')
        leader.save()

        dept.team_leader = leader
        dept.save()

        tech_count = random.randint(3, 7)
        for _ in range(tech_count):
            user = User.objects.create(
                username=fake.unique.user_name(),
                email=fake.unique.email(),
                first_name=fake.first_name(),
                last_name=fake.last_name(),
                user_type=random.choice(USER_TYPE_POOL),
                role=random.choice(ROLE_POOL),
                department=dept,
                phone_number=fake.phone_number(),
            )
            user.set_password('techPass123')
            user.save()