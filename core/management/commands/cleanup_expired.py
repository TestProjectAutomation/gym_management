# core/management/commands/cleanup_expired.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from core.tasks import check_expired_subscriptions, cleanup_old_attendance_records


class Command(BaseCommand):
    help = 'Clean up expired subscriptions and old records'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--subscriptions',
            action='store_true',
            help='Check and expire subscriptions',
        )
        parser.add_argument(
            '--attendance',
            action='store_true',
            help='Clean up old attendance records',
        )
        parser.add_argument(
            '--all',
            action='store_true',
            help='Run all cleanup tasks',
        )
    
    def handle(self, *args, **options):
        self.stdout.write('Starting cleanup...')
        
        if options['subscriptions'] or options['all']:
            self.stdout.write('Checking expired subscriptions...')
            count = check_expired_subscriptions()
            self.stdout.write(self.style.SUCCESS(f'Expired {count} subscriptions'))
        
        if options['attendance'] or options['all']:
            self.stdout.write('Cleaning up attendance records...')
            cleanup_old_attendance_records()
            self.stdout.write(self.style.SUCCESS('Attendance records cleaned up'))
        
        self.stdout.write(self.style.SUCCESS('Cleanup completed'))