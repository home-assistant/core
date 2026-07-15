"""SwitchBotCloudSelect entity."""

from typing import override

from switchbot_api import BatteryCirculatorFanCommands, Device, Remote, SwitchBotAPI

from homeassistant.components.select import SelectEntity
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SwitchbotCloudConfigEntry, SwitchBotCoordinator
from .const import (
    BATTERY_CIRCULATOR_FAN_2_PRO_NIGHT_LIGHT_PARAMETERS_MAP,
    NIGHT_LIGHT_BRIGHT,
    NIGHT_LIGHT_ON,
    NIGHT_LIGHT_SOFT,
    STANDING_FAN_NIGHT_LIGHT_PARAMETERS_MAP,
)
from .entity import SwitchBotCloudEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config: SwitchbotCloudConfigEntry,
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

    _night_light_parameters_map: dict[str, str] = (
        STANDING_FAN_NIGHT_LIGHT_PARAMETERS_MAP
    )
    _attr_entity_category = EntityCategory.CONFIG
    _attr_current_option: str | None = None

    _attr_translation_key = "night_light_control"
    _attr_options = list(_night_light_parameters_map)

    @override
    async def async_select_option(self, option: str) -> None:
        """Select the night light mode."""
        if option == NIGHT_LIGHT_ON:
            para = self._night_light_parameters_map.get(
                NIGHT_LIGHT_BRIGHT
            ) or self._night_light_parameters_map.get(NIGHT_LIGHT_SOFT)
            assert para is not None
            await self.send_api_command(
                BatteryCirculatorFanCommands.SET_NIGHT_LIGHT_MODE,
                parameters=para,
            )
        else:
            await self.send_api_command(
                BatteryCirculatorFanCommands.SET_NIGHT_LIGHT_MODE,
                parameters=self._night_light_parameters_map[option],
            )
        self._attr_current_option = option
        self.async_write_ha_state()

    @override
    def _set_attributes(self) -> None:
        """Set attributes from coordinator data."""
        if self.coordinator.data is None:
            return
        night_status = self.coordinator.data.get("nightStatus")
        # if night_status == NIGHT_LIGHT_ON:
        #     self._attr_current_option = NIGHT_LIGHT_ON
        #     return
        for key, value in self._night_light_parameters_map.items():
            if value == night_status:
                self._attr_current_option = key
                return
        self._attr_current_option = None


class SwitchBotCloudBatteryCirculatorFan2ProNightLight(
    SwitchBotCloudStandingFanNightLight
):
    """SwitchBotCloud Battery Circulator Fan 2 Pro Night Light."""

    _night_light_parameters_map: dict[str, str] = (
        BATTERY_CIRCULATOR_FAN_2_PRO_NIGHT_LIGHT_PARAMETERS_MAP
    )


@callback
def _async_make_entity(
    api: SwitchBotAPI, device: Device | Remote, coordinator: SwitchBotCoordinator
) -> (
    SwitchBotCloudStandingFanNightLight
    | SwitchBotCloudBatteryCirculatorFan2ProNightLight
):
    """Make a SwitchBotCloudSelect entity."""
    if device.device_type == "Standing Fan":
        return SwitchBotCloudStandingFanNightLight(api, device, coordinator)
    if device.device_type == "Battery Circulator Fan 2 Pro":
        return SwitchBotCloudBatteryCirculatorFan2ProNightLight(
            api, device, coordinator
        )
    raise NotImplementedError
