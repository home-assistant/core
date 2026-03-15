"""SwitchBotCloudSelect entity."""

import asyncio
import random
import time

from switchbot_api import Device, KeyPadCommands, SwitchBotAPI

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SwitchbotCloudData, SwitchBotCoordinator
from .const import AFTER_COMMAND_REFRESH, DOMAIN, KEYPAD_KEY_EXPIRY_DURATION_SECONDS
from .entity import SwitchBotCloudEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SwitchBot Cloud entry."""
    data: SwitchbotCloudData = hass.data[DOMAIN][config.entry_id]
    async_add_entities(
        _async_make_entity(data.api, device, coordinator)
        for device, coordinator in data.devices.selects
    )


class SwitchBotCloudKeypad(SwitchBotCloudEntity, SelectEntity):
    """SwitchBotCloud Keypad."""

    default_option: str = "create key"

    _attr_options = [
        default_option,
    ]
    _attr_current_option = _attr_options[0]
    _attr_name: None = None

    _attr_translation_key = "keypad"

    async def async_select_option(self, option: str) -> None:
        """Select an existing key or create a new one."""
        if option == self.default_option:
            password = f"{random.randint(100000, 999999)}"
            now = int(time.time())
            parameters = {
                "name": "PW" + f"{now}"[-8:],
                "type": "disposable",
                "password": password,
                "startTime": now,
                "endTime": now + KEYPAD_KEY_EXPIRY_DURATION_SECONDS,
            }
            await self.send_api_command(
                KeyPadCommands.CREATE_KEY, parameters=parameters
            )
            self._attr_current_option = password
            self._attr_options.append(self._attr_current_option)
        else:
            self._attr_current_option = option
        self.async_write_ha_state()
        await asyncio.sleep(AFTER_COMMAND_REFRESH)
        await self.coordinator.async_request_refresh()

    def _set_attributes(self) -> None:
        """Set attributes from coordinator data."""
        if self.coordinator.data is None:
            return
        options = [self.default_option]
        key_list = self.coordinator.data.get("keyList", [])
        for item in key_list:
            password = item["password"]
            iv = item["iv"]
            key = self._api.aes_128_cbc_decrypt(password, iv)
            status = item["status"]
            if status == "expired":
                key = f"{key} - {status}"
            options.insert(0, key)

        self._attr_options = options
        self._attr_current_option = options[0]


@callback
def _async_make_entity(
    api: SwitchBotAPI, device: Device, coordinator: SwitchBotCoordinator
) -> SwitchBotCloudKeypad:
    """Make a SwitchBotCloudSelect entity."""
    return SwitchBotCloudKeypad(api, device, coordinator)
