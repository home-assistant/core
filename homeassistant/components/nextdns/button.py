"""Support for the NextDNS service."""

from typing import override

from aiohttp import ClientError
from aiohttp.client_exceptions import ClientConnectorError
from nextdns import ApiError, InvalidApiKeyError

from homeassistant.components.button import ButtonEntity, ButtonEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import NextDnsConfigEntry
from .const import DOMAIN
from .entity import NextDnsEntity

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
    """Add NextDNS entities from a config_entry."""
    for subentry_id, profile_data in entry.runtime_data.profiles.items():
        coordinator = profile_data.status
        async_add_entities(
            [NextDnsButton(coordinator, CLEAR_LOGS_BUTTON)],
            config_subentry_id=subentry_id,
        )


class NextDnsButton(NextDnsEntity, ButtonEntity):
    """Define an NextDNS button."""

    @override
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
