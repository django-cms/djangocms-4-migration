import logging

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import migrations
from djangocms_versioning.constants import ARCHIVED, DRAFT, PUBLISHED

from djangocms_4_migration.helpers import get_or_create_migration_user


logger = logging.getLogger(__name__)

CMS_3_PUBLISHER_STATE_DEFAULT = 0
CMS_3_PUBLISHER_STATE_DIRTY = 1
# Page was marked published, but some of page parents are not.
CMS_3_PUBLISHER_STATE_PENDING = 4

USERNAME_FIELD = getattr(get_user_model(), "USERNAME_FIELD", "username")


def forwards(apps, schema_editor):
    db_alias = schema_editor.connection.alias
    PageContent = apps.get_model("cms", "PageContent")
    Version = apps.get_model("djangocms_versioning", "Version")
    PageData = apps.get_model("djangocms_4_migration", "PageData")
    User = get_user_model()
    ContentType = apps.get_model('contenttypes', 'ContentType')

    page_content_contenttype = ContentType.objects.get(app_label='cms', model='pagecontent')

    def _handle_draft_page(existing_title):
        # If there's no published version.
        if not existing_title.opposite_number_id:

            # Get the pages opposite number if one exists i.e. another language has been published in the past
            # and created one It's just not available to the title
            if existing_title.page_opposite_number_id:
                # assign to the published variant of the page
                page_content.page_id = existing_title.page_opposite_number_id
                page_content.save()

            # Create a version
            _create_version(page_content, state=DRAFT)
            return

        related_published_title = PageContent.objects.using(db_alias).get(
            pk=existing_title.opposite_number_id
        )

        # Detach the page and Assign the published page
        page_content.page = related_published_title.page
        page_content.save()

        # if the date is after the published version, it contains changes that need to be kept
        if existing_title.publisher_state == CMS_3_PUBLISHER_STATE_DIRTY:
            # Create a draft version
            _create_version(page_content, state=DRAFT, number=2)

    def _handle_public_page(existing_title):
        state = PUBLISHED
        if not existing_title.published:
            state = ARCHIVED
        _create_version(page_content, state=state)

    def _create_version(page_content, state=DRAFT, number=1):
        # Find the user
        try:
            created_by = User.objects.using(db_alias).get(
                **{USERNAME_FIELD: page_content.page.created_by}
            )
        except:
            # Use the first super user as the author as a fall back
            # The create page api allocates 'python-api' as the user!
            logger.warning("User {} not found, falling back.".format(page_content.page.created_by))
            created_by, created = get_or_create_migration_user(user_model=User)

        logger.info("Creating version for new title: {}".format(page_content.pk))

        # Create a new version for the page
        # Recheck
        Version.objects.using(db_alias).create(
            created_by=created_by,
            state=state,
            number=number,
            object_id=page_content.pk,
            content_type=page_content_contenttype,
        )

    # CAVEAT: Draft is always seen before published as that is how CMS 3.5 created them.
    for existing_title in PageData.objects.using(db_alias).all():
        """
        If Title was published keep it and create a version
        If Title was not published
        """
        logger.info("Existing title: {}".format(str(existing_title.title_id)))

        page_content = PageContent.objects.using(db_alias).get(
            pk=existing_title.title_id
        )

        # If this is the draft page
        if existing_title.publisher_is_draft:
            _handle_draft_page(existing_title)
        # Otherwise this is the published page
        else:
            _handle_public_page(existing_title)


class Migration(migrations.Migration):

    dependencies = [
        ('djangocms_4_migration', '0002_collect_removed_data_data_migration'),
        ('cms', '0034_remove_pagecontent_placeholders'), # Run after the CMS4 migrations
        ('djangocms_versioning', '0015_version_modified'),  # Ensure the modified field is present
    ]

    operations = [
        migrations.RunPython(forwards),
    ]

