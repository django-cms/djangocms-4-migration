# django CMS 4 Migration

**Warning:** If the migration process fails to complete you will not be able to undo the changes without reloading a database backup. We cannot be held accountable for any data loss sustained when running the commands provided in this project. Please keep a database backup before running any commands provided by this package.

## When do I need this package?
This package is designed to migrate a django CMS 3.5+ project to django CMS 4.0.

## What does this package do?
- Keeps any draft and published content, ensuring that any new draft changes are kept as a new draft version in djangocms_versioning.
- Creates aliases for static placeholder
- Migrates alias plugins
- Runs django CMS' migrations

## Limitations
Due to the nature of the changes between django CMS 3.5+ and 4.0 the package will fail to function if an incompatible package is installed.

This may require you to:
 - Fork or copy and modify this package to work with any bespoke requirements your project has (we may accept these changes back for popular packages as a configurable option)
 - Ensure that all installed packages for your project are

## Prerequisites
Require knowledge of the changes and new features in 4.0:
- New cms app configuration
- Revised Page, Title (Now named PageContent) and Placeholder relationships

Requires knowledge of django CMS Versioning
- Grouper and content model terms
- Understanding how versioning selects published content

### Install the following packages
The following packages are not yet officially released, they need to be installed directly from the repository. We need your help to make packages v4.0 compatible and to provide documentation for the wider community!

django CMS 4.0+
```
pip install django-cms
```

djangocms-text-ckeditor
```
pip install djangocms-text-ckeditor
```

djangocms-versioning
```
pip install djangocms-versioning
```

djangocms-alias
```
pip install djangocms-alias
```

## Installation
**Warning**: This package can leave your DB in a corrupted state if used incorrectly, be sure to backup any databases prior to running any commands listed here!

First install this package in your project
```
pip install git+https://github.com/django-cms/djangocms-4-migration
```

## Configuration

Add the migration tool to `INSTALLED_APPS` temporarily. In your `settings.py` make sure that it is listed. You can remove it after the migration process.
```
INSTALLED_APPS = [
    ...,
    "djangocms_4_migration",
    "djangocms_versioning",
    "djangocms_alias",
    ...,
]
CMS_CONFIRM_VERSION4 = True
```

If you have a custom user model, you should designate a "migration user" by specifying the user ID in your settings like so:

```
CMS_MIGRATION_USER_ID = <user id>
```

If you want to adjust data to get the migration running in your project, there are 2 function-points available:

```
CMS_MIGRATION_PROCESS_MIGRATION_PREPARATION = "mymodule.myfunction2"
CMS_MIGRATION_PROCESS_PAGE_REFERENCES = "mymodule.myfunction"
```

The latter function is supplied with parameters `page` and `replacement_page`.

## Running
Simply run the following command to run the data migration.
**Note:** This command calls the django migrate command, this is because it has to run commands that save information that would have been lost by running the cms migrations directly.
```
python manage.py cms4_migration
```

You can ignore warnings of the form
```
UserWarning: No user has been supplied when creating a new AliasContent object.
No version could be created. Make sure that the creating code also creates a
Version objects or use AliasContent.objects.with_user(user).create(...)
```

## Common solutions for django CMS 4.0 compatibility

Import PageContent in a backwards compatible way (Title).
```python

# django CMS v4
try:
    from cms.models import PageContent
# django CMS 3.x
except ImportError:
    from cms.models import Title as PageContent
```
