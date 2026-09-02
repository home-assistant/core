"""Initialize repositories."""

from collections.abc import Callable
from typing import TYPE_CHECKING

from ..enums import HacsCategory
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
REPOSITORY_CLASSES: dict[HacsCategory, Callable[[HacsBase, str], HacsRepository]] = {
    HacsCategory.THEME: HacsThemeRepository,
    HacsCategory.INTEGRATION: HacsIntegrationRepository,
    HacsCategory.PYTHON_SCRIPT: HacsPythonScriptRepository,
    HacsCategory.APPDAEMON: HacsAppdaemonRepository,
    HacsCategory.PLUGIN: HacsPluginRepository,
    HacsCategory.TEMPLATE: HacsTemplateRepository,
}
