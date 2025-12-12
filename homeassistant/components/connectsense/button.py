from __future__ import annotations

import logging

from rebooterpro_async import RebooterDecodeError

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .entity import ConnectSenseEntity
from .models import ConnectSenseConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant, entry: ConnectSenseConfigEntry, async_add_entities
):
    data = entry.runtime_data
    async_add_entities(
        [RebooterRebootButton(hass, data.coordinator, entry, data.client)]
    )


class RebooterRebootButton(ConnectSenseEntity, ButtonEntity):
    _attr_name = "Reboot Now"
    _attr_icon = "mdi:restart"
    _attr_should_poll = False
    _attr_device_class = ButtonDeviceClass.RESTART

    def __init__(self, hass, coordinator, entry, client):
        super().__init__(hass, coordinator, entry)
        self._client = client
        base_uid = entry.unique_id or entry.entry_id
        self._attr_unique_id = f"{base_uid}_reboot"

    async def async_press(self) -> None:
        try:
            await self._client.reboot_outlet()
        except RebooterDecodeError as exc:
            # Some firmware returns plain "OK" instead of JSON; treat as success.
            _LOGGER.debug("Non-JSON /control response treated as success: %s", exc)
        except Exception as exc:
            raise HomeAssistantError("Device rejected reboot request.") from exc
        _LOGGER.debug("Reboot requested for %s", self.entry.entry_id)
