from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "django CMS 3.5+ to 4.0 Migration"

    def handle(self, *args, **options):
        # Prepare the DB by cleaning it up before running anything
        call_command("migration_preparation")

        # Run standard django migrations
        call_command("migrate")

        # Migrate the CMS 3.5 Alias Plugin instances
        call_command("migrate_alias_plugins")

        # Migrate static placeholders
        call_command("migrate_static_placeholders")

        # Clean up after the migration has finished
        call_command("migration_cleanup")
        call_command("remove_unlinked_placeholders")
