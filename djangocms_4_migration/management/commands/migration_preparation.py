import logging

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import connection


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Run before migrations are applied"

    def handle(self, *args, **options):
        logger.info("Attempting to remove djangocms_history")
        # Code is too different for: call_command('migrate', 'djangocms_history', 'zero')
        try:
            with connection.cursor() as cursor:
                cursor.execute("DROP table djangocms_history_placeholderaction;")
                cursor.execute("DROP table djangocms_history_placeholderoperation;")
        except:
            logger.info("djangocms_history already removed")

        custom_function = getattr(settings, "CMS_MIGRATION_PROCESS_MIGRATION_PREPARATION", None)
        if custom_function:
            module, function = custom_function.rsplit(".", 1)
            getattr(
                __import__(module, fromlist=[""]),
                function,
            )()
