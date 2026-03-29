# core/management/commands/generate_reports.py
from django.core.management.base import BaseCommand
from django.utils import timezone
from core.services import DashboardService
from core.models import Gym
import csv
from datetime import timedelta


class Command(BaseCommand):
    help = 'Generate reports for all gyms'
    
    def add_arguments(self, parser):
        parser.add_argument(
            '--days',
            type=int,
            default=30,
            help='Number of days for report',
        )
        parser.add_argument(
            '--output',
            type=str,
            default='report.csv',
            help='Output file name',
        )
    
    def handle(self, *args, **options):
        self.stdout.write('Generating reports...')
        
        gyms = Gym.objects.filter(is_active=True)
        days = options['days']
        
        report_data = []
        
        for gym in gyms:
            stats = DashboardService.get_dashboard_stats(gym)
            attendance_stats = DashboardService.get_attendance_stats(gym, days)
            revenue_stats = DashboardService.get_revenue_stats(gym, days)
            
            report_data.append({
                'gym_name': gym.name,
                'total_members': stats['total_members'],
                'active_members': stats['active_members'],
                'total_coaches': stats['total_coaches'],
                'active_subscriptions': stats['active_subscriptions'],
                'revenue_today': stats['revenue_today'],
                'revenue_month': stats['revenue_month'],
                'attendance_rate': sum(s['checkins'] for s in attendance_stats) / days if days > 0 else 0,
            })
        
        # Write to CSV
        filename = options['output']
        with open(filename, 'w', newline='', encoding='utf-8') as csvfile:
            fieldnames = ['gym_name', 'total_members', 'active_members', 'total_coaches', 
                         'active_subscriptions', 'revenue_today', 'revenue_month', 'attendance_rate']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(report_data)
        
        self.stdout.write(self.style.SUCCESS(f'Report saved to {filename}'))