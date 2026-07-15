"""SwitchBotCloudSelect entity."""

from typing import override

from switchbot_api import BatteryCirculatorFanCommands, Device, Remote, SwitchBotAPI

from homeassistant.components.select import SelectEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SwitchBotCoordinator
from .const import NIGHT_LIGHT_PARAMETERS_MAP
from .entity import SwitchBotCloudEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SwitchBot Cloud entry."""
    data = config.runtime_data
    async_add_entities(
        _async_make_entity(data.api, device, coordinator)
        for device, coordinator in data.devices.selects
    )


class SwitchBotCloudStandingFanNightLight(SwitchBotCloudEntity, SelectEntity):
    """SwitchBotCloud Standing Fan Night Light."""

    _attr_options = list(NIGHT_LIGHT_PARAMETERS_MAP)
    _attr_current_option: str | None = _attr_options[0]

    _attr_translation_key = "night_light_control"

    @override
    async def async_select_option(self, option: str) -> None:
        """Select the night light mode."""

        await self.send_api_command(
            BatteryCirculatorFanCommands.SET_NIGHT_LIGHT_MODE,
            parameters=NIGHT_LIGHT_PARAMETERS_MAP[option],
        )
        self._attr_current_option = option
        self.async_write_ha_state()

    @override
    def _set_attributes(self) -> None:
        """Set attributes from coordinator data."""
        if self.coordinator.data is None:
            return
        for key, value in NIGHT_LIGHT_PARAMETERS_MAP.items():
            if value == self.coordinator.data["nightStatus"]:
                self._attr_current_option = key
                return
        self._attr_current_option = None


@callback
def _async_make_entity(
    api: SwitchBotAPI, device: Device | Remote, coordinator: SwitchBotCoordinator
) -> SwitchBotCloudStandingFanNightLight:
    """Make a SwitchBotCloudSelect entity."""
    return SwitchBotCloudStandingFanNightLight(api, device, coordinator)
