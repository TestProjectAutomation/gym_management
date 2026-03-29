from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'



# # core/apps.py
# from django.apps import AppConfig
# from django.utils.translation import gettext_lazy as _


# class CoreConfig(AppConfig):
#     default_auto_field = 'django.db.models.BigAutoField'
#     name = 'core'
#     verbose_name = _("Gym Management System")
    
#     def ready(self):
#         """Import signals when app is ready"""
#         import core.signals