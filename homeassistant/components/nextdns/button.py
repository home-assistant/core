"""Support for the NextDNS service."""

from __future__ import annotations

from aiohttp import ClientError
from aiohttp.client_exceptions import ClientConnectorError
from nextdns import AnalyticsStatus, ApiError, InvalidApiKeyError

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import NextDnsConfigEntry
from .const import DOMAIN
from .coordinator import NextDnsUpdateCoordinator

PARALLEL_UPDATES = 1

CLEAR_LOGS_BUTTON = ButtonEntityDescription(
    key="clear_logs",
    translation_key="clear_logs",
    entity_category=EntityCategory.CONFIG,
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: NextDnsConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Add aNextDNS entities from a config_entry."""
    coordinator = entry.runtime_data.status

    async_add_entities([NextDnsButton(coordinator, CLEAR_LOGS_BUTTON)])


class NextDnsButton(
    CoordinatorEntity[NextDnsUpdateCoordinator[AnalyticsStatus]], ButtonEntity
):
    """Define an NextDNS button."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: NextDnsUpdateCoordinator[AnalyticsStatus],
        description: ButtonEntityDescription,
    ) -> None:
        """Initialize."""
        super().__init__(coordinator)
        self._attr_device_info = coordinator.device_info
        self._attr_unique_id = f"{coordinator.profile_id}_{description.key}"
        self.entity_description = description

    async def async_press(self) -> None:
        """Trigger cleaning logs."""
        try:
            await self.coordinator.nextdns.clear_logs(self.coordinator.profile_id)
        except (
            ApiError,
            ClientConnectorError,
            TimeoutError,
            ClientError,
        ) as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="method_error",
                translation_placeholders={
                    "entity": self.entity_id,
                    "error": repr(err),
                },
            ) from err
        except InvalidApiKeyError:
            self.coordinator.config_entry.async_start_reauth(self.hass)
