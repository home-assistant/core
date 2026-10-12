"""Support for Watergate buttons."""

import logging
from typing import override

from watergate_local_api import WatergateApiException, WatergateIndeterminateError

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .const import DOMAIN
from .coordinator import WatergateConfigEntry, WatergateDataCoordinator
from .entity import WatergateEntity

_LOGGER = logging.getLogger(__name__)

ENTITY_NAME = "reboot"
PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: WatergateConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the Watergate button entity."""
    async_add_entities([SonicRebootButton(config_entry.runtime_data)])


class SonicRebootButton(WatergateEntity, ButtonEntity):
    """Button to reboot the Sonic."""

    _attr_device_class = ButtonDeviceClass.RESTART
    _attr_translation_key = "reboot"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(self, coordinator: WatergateDataCoordinator) -> None:
        """Initialize the button."""
        super().__init__(coordinator, ENTITY_NAME)

    @override
    async def async_press(self) -> None:
        """Reboot the device."""
        try:
            await self._api_client.async_reboot()
        except WatergateIndeterminateError:
            # The device drops the connection while rebooting, so a lost response
            # is expected. The client does not retry; the device state is refreshed
            # on the next poll or when the device reports it is back online.
            _LOGGER.debug("Reboot sent, no response received (device is restarting)")
        except WatergateApiException as exc:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="reboot_failed",
            ) from exc
