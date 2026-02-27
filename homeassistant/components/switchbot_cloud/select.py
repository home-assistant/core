"""SwitchBotCloudSelect entity."""

from switchbot_api import Device, Remote, SwitchBotAPI

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SwitchbotCloudData, SwitchBotCoordinator
from .const import DOMAIN
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

    _attr_options = [
        "create key",
    ]
    _attr_current_option = _attr_options[0]

    async def async_select_option(self, option: str) -> None:
        """Show existed key & create key."""

    def _set_attributes(self) -> None:
        """Set attributes from coordinator data."""
        if self.coordinator.data is None:
            return
        options = ["Create Key"]
        keyList = self.coordinator.data["keyList"]
        for item in keyList:
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
    api: SwitchBotAPI, device: Device | Remote, coordinator: SwitchBotCoordinator
) -> SwitchBotCloudKeypad:
    """Make a SwitchBotCloudSelect entity."""
    return SwitchBotCloudKeypad(api, device, coordinator)
