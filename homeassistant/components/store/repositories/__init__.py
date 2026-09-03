"""Initialize repositories."""

from collections.abc import Callable
from typing import TYPE_CHECKING

from ..enums import RepositoryCategory
from .appdaemon import HacsAppdaemonRepository
from .base import HacsRepository
from .integration import HacsIntegrationRepository
from .plugin import HacsPluginRepository
from .python_script import HacsPythonScriptRepository
from .template import HacsTemplateRepository
from .theme import HacsThemeRepository

if TYPE_CHECKING:
    from ..base import HacsBase

# The category classes all take (hacs, full_name), which the base class does not.
REPOSITORY_CLASSES: dict[
    RepositoryCategory, Callable[[HacsBase, str], HacsRepository]
] = {
    RepositoryCategory.THEME: HacsThemeRepository,
    RepositoryCategory.INTEGRATION: HacsIntegrationRepository,
    RepositoryCategory.PYTHON_SCRIPT: HacsPythonScriptRepository,
    RepositoryCategory.APPDAEMON: HacsAppdaemonRepository,
    RepositoryCategory.PLUGIN: HacsPluginRepository,
    RepositoryCategory.TEMPLATE: HacsTemplateRepository,
}
