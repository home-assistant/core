from __future__ import annotations

import logging

from rebooterpro_async import RebooterDecodeError

from homeassistant.components.button import ButtonDeviceClass, ButtonEntity
from homeassistant.const import CONF_HOST
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo

from .const import DOMAIN
from .device_client import async_get_client
from .models import ConnectSenseConfigEntry

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(hass, entry: ConnectSenseConfigEntry, async_add_entities):
    async_add_entities([RebooterRebootButton(hass, entry)])


class RebooterRebootButton(ButtonEntity):
    _attr_has_entity_name = True
    _attr_name = "Reboot Now"
    _attr_icon = "mdi:restart"
    _attr_should_poll = False
    _attr_device_class = ButtonDeviceClass.RESTART

    def __init__(self, hass, entry):
        self.hass = hass
        self.entry = entry
        base_uid = entry.unique_id or entry.entry_id
        self._attr_unique_id = f"{base_uid}_reboot"

    @property
    def device_info(self) -> DeviceInfo:
        host = self.entry.data[CONF_HOST]
        uid = self.entry.unique_id or host
        return DeviceInfo(
            identifiers={(DOMAIN, uid)},
            name=self.entry.title or f"Rebooter Pro {uid}",
            manufacturer="Grid Connect",
            model="Rebooter Pro"
        )

    async def async_press(self) -> None:
        try:
            client = await async_get_client(self.hass, self.entry)
            await client.reboot_outlet()
        except RebooterDecodeError as exc:
            # Some firmware returns plain "OK" instead of JSON; treat as success.
            _LOGGER.debug("Non-JSON /control response treated as success: %s", exc)
        except Exception as exc:
            raise HomeAssistantError("Device rejected reboot request.") from exc
        _LOGGER.debug("Reboot requested for %s", self.entry.entry_id)
