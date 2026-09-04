"""Base class for KNX entity suggestion providers."""

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, ClassVar

from homeassistant.core import HomeAssistant

from .const import ProviderResult

if TYPE_CHECKING:
    from ...knx_module import KNXModule


class SuggestionProvider(ABC):
    """Generate entity suggestions from a specific data source.

    Providers gather their data sources themselves (eg. project data
    or existing entity configurations) and report source specific
    information for empty result hints in `ProviderResult["hints"]`.
    """

    provider_id: ClassVar[str]

    @abstractmethod
    async def async_get_suggestions(
        self, hass: HomeAssistant, knx: KNXModule
    ) -> ProviderResult:
        """Generate entity suggestions."""
