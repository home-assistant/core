"""Initialize repositories."""

from ..enums import HacsCategory
from .appdaemon import HacsAppdaemonRepository
from .base import HacsRepository
from .integration import HacsIntegrationRepository
from .plugin import HacsPluginRepository
from .python_script import HacsPythonScriptRepository
from .template import HacsTemplateRepository
from .theme import HacsThemeRepository

REPOSITORY_CLASSES: dict[HacsCategory, type[HacsRepository]] = {
    HacsCategory.THEME: HacsThemeRepository,
    HacsCategory.INTEGRATION: HacsIntegrationRepository,
    HacsCategory.PYTHON_SCRIPT: HacsPythonScriptRepository,
    HacsCategory.APPDAEMON: HacsAppdaemonRepository,
    HacsCategory.PLUGIN: HacsPluginRepository,
    HacsCategory.TEMPLATE: HacsTemplateRepository,
}
