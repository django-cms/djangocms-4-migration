import logging

from django.core.management.base import BaseCommand
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth import get_user_model
from django.contrib.sites.models import Site
from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from cms.api import add_plugin
from cms.models import (
    AliasPluginModel,
    CMSPlugin,
    PageContent,
    Placeholder,
)
from cms.utils.i18n import get_language_list

from djangocms_alias.models import (
    Alias as AliasModel,
    AliasContent,
    AliasPlugin as CMS4AliasPluginModel,
    Category,
)
from djangocms_alias.utils import is_versioning_enabled

from djangocms_4_migration.models import PageData


logger = logging.getLogger(__name__)

User = get_user_model()

src_alias_count = 0
reference_alias_count = 0
new_src_alias_plugins_count = 0
new_ref_alias_plugins_count = 0


def _create_site_category(site, language):
    category_name = f"{site.name}-Migrated-{language}"
    category = (
        Category.objects.language(language)
        .filter(translations__name=category_name)
        .first()
    )
    if not category:
        category = Category.objects.language(language).create(
            name=category_name,
        )
    return category


def create_new_alias_for_source_plugins(old_plugin, new_alias_grouper):
    global src_alias_count

    try:
        page_details = PageData.objects.get(
            page_id=old_plugin.placeholder.source.page.id, language=old_plugin.language
        )

        # get published/draft pages for the old Src plugin
        src_plugin_pagecontents = PageContent._base_manager.filter(
            page_id=page_details.page_id, language=old_plugin.language
        )

        for src_plugin_pagecontent in src_plugin_pagecontents:
            src_plugin = None
            try:
                # Get the placeholder with slot name from the published
                src_plugin_placeholder = Placeholder.objects.get(
                    slot=old_plugin.placeholder.slot,
                    content_type=ContentType.objects.get(
                        app_label="cms", model="pagecontent"
                    ),
                    object_id=src_plugin_pagecontent.id,
                )

            except ObjectDoesNotExist:
                logger.error(
                    "Error placeholder for the plugin {} Doesn't exist in published pagecontent {}".format(
                        old_plugin.id, src_plugin_pagecontent.id
                    )
                )
                return
            # check if the source plugin exists at the same position in the published/draft page
            try:
                src_plugin = CMSPlugin.objects.get(
                    placeholder_id=src_plugin_placeholder.id,
                    language=old_plugin.language,
                    position=old_plugin.position,
                    plugin_type=old_plugin.plugin_type,
                )
            except ObjectDoesNotExist:
                logger.error(
                    "Error plugin {} Doesn't exist at the position in placeholder {}".format(
                        old_plugin.id, src_plugin_placeholder.id
                    )
                )

            # Add the count to check total source plugins traversed to migrate to cms4
            src_alias_count += 1
            if src_plugin:
                # if the plugin of the same plugin type is found in the page and in same placeholder holder
                # at the same position create the cms4 Alias plugin
                create_new_alias_plugin(
                    src_plugin, new_alias_grouper, is_src_plugin=True
                )

    except ObjectDoesNotExist:
        logger.error(
            "pagedata object doesn;t exist for plugin {}".format(old_plugin.id)
        )
        return


def create_new_alias_plugin(old_plugin, new_alias_grouper, is_src_plugin=False):
    """
    Create cms4 alias plugin and replace the cms3 reference plugin with new cms4 alias plugin

    :param old_plugin: cms3 plugin
    :param new_alias_grouper:  Alias instance for cms4
    :return: None
    """
    global reference_alias_count
    global new_ref_alias_plugins_count
    global new_src_alias_plugins_count

    if not is_src_plugin:
        # increment reference count, if the cms4 alias plugin is being added for cms3 reference alias
        reference_alias_count += 1

    # Create a new cms4 alias plugin in place of the old cms 3 plugin
    new_plugin = add_plugin(
        old_plugin.placeholder,
        "Alias",
        language=old_plugin.language,
        alias=new_alias_grouper,
    )
    # Store the plugins details to replace it
    old_plugin_position = old_plugin.position
    old_plugin_id = old_plugin.id

    # Delete the old plugin
    if new_plugin:
        if is_src_plugin:
            # Add the target cms4alias plugin count for  cms3 source plugins
            new_src_alias_plugins_count += 1
        else:
            # Add the target cms4alias plugin count for  reference alias
            new_ref_alias_plugins_count += 1
        logger.info("Deleting old plugin: {}".format(old_plugin_id))
        old_plugin.delete()

    # Move the cms 4 alias into the same place as the cms 3 plugin
    new_plugin.position = old_plugin_position
    new_plugin.save()

    logger.info(
        "Creating cms4 alias plugin: {}-{} for cms3plugin {}".format(
            new_plugin.id,
            new_plugin.plugin_type,
            old_plugin_id,
        )
    )


def create_reference_alias_plugins(old_source_plugin, new_alias_grouper):
    """
    Create cms4 Alias plugin for cms3 alias references
    """
    for old_alias_reference in AliasPluginModel.objects.filter(
        plugin_id=old_source_plugin
    ):
        reference_plugin = CMSPlugin.objects.get(
            id=old_alias_reference.cmsplugin_ptr_id
        )
        # Create Alias plugin for the reference plugin at the reference plugin location and delete the reference plugin
        create_new_alias_plugin(reference_plugin, new_alias_grouper)

    # Create Alias plugin for the Alias source plugin at the source plugin location and delete the source plugin
    create_new_alias_for_source_plugins(old_source_plugin, new_alias_grouper)


def get_child_plugins(plugin):
    """
    :param plugin: CMSPlugin Object
    :return: Queryset for Child plugin objects for this plugin
    """
    child_plugin_queryset = CMSPlugin.objects.filter(parent_id=plugin.id)
    return child_plugin_queryset


def process_old_alias_sources(site, language, site_plugin_queryset):
    # Creat ea category container
    cms4_alias_category = _create_site_category(site, language)

    for old_plugin in site_plugin_queryset:
        page_title = old_plugin.placeholder.source.title
        # Create Alias Grouper
        cms4_alias_name = f"{old_plugin.plugin_type}-{page_title}"
        alias_grouper = AliasModel.objects.create(
            category=cms4_alias_category,
        )
        alias_grouper.save()
        # Create Alias Content
        alias_content = AliasContent.objects.create(
            alias=alias_grouper,
            name=cms4_alias_name,
            language=language,
        )
        alias_content.save()
        # Added Child Plugins to alias content if they exists
        child_plugins = get_child_plugins(old_plugin)
        plugins = [old_plugin]
        if child_plugins:
            for plugin in child_plugins:
                plugins.append(plugin)
                # Added second level child plugin handling
                second_level_child_plugins = get_child_plugins(plugin)
                if second_level_child_plugins:
                    for child_plugin in second_level_child_plugins:
                        plugins.append(child_plugin)
        alias_content.populate(plugins=plugins)
        alias_content.save()

        if is_versioning_enabled():
            from djangocms_versioning.models import Version

            # Create version
            changed_by = User.objects.get(
                **{User.USERNAME_FIELD: old_plugin.placeholder.source.changed_by}
            )
            version = Version.objects.create(
                content=alias_content, created_by=changed_by
            )
            version.publish(changed_by)

        # create csm4 alias plugins for cms3 alias references
        create_reference_alias_plugins(old_plugin, alias_grouper)


def _process_sites(plugin_id_list):
    for site in Site.objects.all():
        # Sites Placeholders
        logger.info("Processing site: {}".format(site.id))

        sites_placeholders = [
            placeholders.pk
            for pagecontent in PageContent._base_manager.filter(
                page__node__site_id=site.id
            )
            for placeholders in pagecontent.get_placeholders()
        ]
        for language in get_language_list(site.id):
            # Get all plugins in the current site
            site_plugin_queryset = CMSPlugin.objects.filter(
                placeholder__in=sites_placeholders,
                pk__in=plugin_id_list,
                language=language,
            )
            logger.info(
                "Processing Language: {} Plugin count: {}".format(
                    language, site_plugin_queryset.count()
                )
            )

            process_old_alias_sources(site, language, site_plugin_queryset)


class Command(BaseCommand):
    """
    For each unique djangocms 3.5 alias plugin instance in each site
        Replace all pages where the djangocms 3.5 alias plugin exist

    Terms: Alias Reference, Alias Source
    """

    help = "Run after migrations are applied"

    def handle(self, *args, **options):
        with transaction.atomic():
            # Alias source plugin list
            plugin_id_list = list(
                AliasPluginModel.objects.values_list("plugin_id", flat=True).order_by(
                    "plugin_id"
                )
            )
            alias_source_total = len(plugin_id_list)
            # Alias references list count
            alias_reference_total = AliasPluginModel.objects.count()
            old_stats = {
                "old_alias_source_count": alias_source_total,
                # 'old_alias_reference_count': alias_reference_total,
                "old_alias_target_count": alias_reference_total + alias_source_total,
                "src_alias_count": alias_source_total,
                "reference_alias_count": alias_reference_total,
            }
            new_stats = {
                # AliasModel list count should match old_alias_source_count
                "new_alias_source_count": 0,
                # CMS4AliasPluginModel list count should match old_alias_target_count
                "new_alias_plugin_target_count": 0,
                "src_alias_count": 0,
                "reference_alias_count": 0,
                "new_src_alias_plugins_count": 0,
                "new_ref_alias_plugins_count": 0,
            }
            # Do the work
            _process_sites(plugin_id_list)
            # Finalise stats
            new_stats["new_alias_source_count"] = AliasContent.objects.count()
            # CMS4 Alias Plugin count is compared with all source and reference plugins because
            # in the CMS 3 implementation the source is a plugin that is then references to.
            # In CMS 4 the source is the Alias instance not a plugin on a page.
            new_stats["new_alias_plugin_target_count"] = (
                CMS4AliasPluginModel.objects.count()
            )
            new_stats["src_alias_count"] = src_alias_count
            new_stats["reference_alias_count"] = reference_alias_count
            new_stats["new_ref_alias_plugins_count"] = new_ref_alias_plugins_count
            new_stats["new_src_alias_plugins_count"] = new_src_alias_plugins_count
            logger.info("old stats: {}".format(old_stats))
            logger.info("new stats: {}".format(new_stats))
