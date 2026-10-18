"""Initialize repositories."""

from collections.abc import Callable
from typing import TYPE_CHECKING

from ..enums import RepositoryCategory
from .base import Repository
from .integration import IntegrationRepository
from .plugin import PluginRepository
from .template import TemplateRepository
from .theme import ThemeRepository

if TYPE_CHECKING:
    from ..base import MarketplaceManager

# The category classes all take (marketplace, full_name), which the base class does not.
REPOSITORY_CLASSES: dict[
    RepositoryCategory, Callable[[MarketplaceManager, str], Repository]
] = {
    RepositoryCategory.THEME: ThemeRepository,
    RepositoryCategory.INTEGRATION: IntegrationRepository,
    RepositoryCategory.PLUGIN: PluginRepository,
    RepositoryCategory.TEMPLATE: TemplateRepository,
}
