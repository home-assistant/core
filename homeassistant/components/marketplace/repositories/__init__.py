"""Initialize repositories."""

from collections.abc import Callable
from typing import TYPE_CHECKING

from ..enums import RepositoryCategory
from .appdaemon import AppdaemonRepository
from .base import Repository
from .integration import IntegrationRepository
from .plugin import PluginRepository
from .python_script import PythonScriptRepository
from .template import TemplateRepository
from .theme import ThemeRepository

if TYPE_CHECKING:
    from ..base import StoreManager

# The category classes all take (store, full_name), which the base class does not.
REPOSITORY_CLASSES: dict[
    RepositoryCategory, Callable[[StoreManager, str], Repository]
] = {
    RepositoryCategory.THEME: ThemeRepository,
    RepositoryCategory.INTEGRATION: IntegrationRepository,
    RepositoryCategory.PYTHON_SCRIPT: PythonScriptRepository,
    RepositoryCategory.APPDAEMON: AppdaemonRepository,
    RepositoryCategory.PLUGIN: PluginRepository,
    RepositoryCategory.TEMPLATE: TemplateRepository,
}
