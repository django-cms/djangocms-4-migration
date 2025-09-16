import logging

from django.core.management.base import BaseCommand
from django.db.models import ProtectedError

from cms.models import (
    Placeholder,
)


logger = logging.getLogger(__name__)


def _delete_unlinked_placeholders():
    # Get any orphaned clipboards that have been incorrectly
    # linked to a user in the migration from 3 to 4.
    placeholders = Placeholder.objects.filter(slot="clipboard")

    logger.info(f"Orphaned placeholders found: {placeholders.count()}")

    for placeholder in placeholders:
        try:
            logger.debug(f"Deleting Placeholder {placeholder.id}")
            placeholder.delete()
        except ProtectedError as err:
            logger.error(f"Couldn't Placeholder {placeholder.id} {err}")


class Command(BaseCommand):
    help = "Delete all orphaned placeholders that are not linked to anything"

    def handle(self, *args, **options):
        logger.info("Running placeholder cleanup")

        _delete_unlinked_placeholders()
