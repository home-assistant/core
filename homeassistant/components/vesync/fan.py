"""Support for VeSync fans."""

from __future__ import annotations

import logging
import math
from typing import Any

from pyvesync.vesyncbasedevice import VeSyncBaseDevice

from homeassistant.components.fan import FanEntity, FanEntityFeature
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.util.percentage import (
    percentage_to_ranged_value,
    ranged_value_to_percentage,
)
from homeassistant.util.scaling import int_states_in_range

from .const import (
    DEV_TYPE_TO_HA,
    DOMAIN,
    SKU_TO_BASE_DEVICE,
    VS_COORDINATOR,
    VS_DEVICES,
    VS_DISCOVERY,
)
from .coordinator import VeSyncDataCoordinator
from .entity import VeSyncBaseEntity

_LOGGER = logging.getLogger(__name__)

FAN_MODE_AUTO = "auto"
FAN_MODE_SLEEP = "sleep"
FAN_MODE_PET = "pet"
FAN_MODE_TURBO = "turbo"

PRESET_MODES = {
    "LV-PUR131S": [FAN_MODE_AUTO, FAN_MODE_SLEEP],
    "Core200S": [FAN_MODE_SLEEP],
    "Core300S": [FAN_MODE_AUTO, FAN_MODE_SLEEP],
    "Core400S": [FAN_MODE_AUTO, FAN_MODE_SLEEP],
    "Core600S": [FAN_MODE_AUTO, FAN_MODE_SLEEP],
    "EverestAir": [FAN_MODE_AUTO, FAN_MODE_SLEEP, FAN_MODE_TURBO],
    "Vital200S": [FAN_MODE_AUTO, FAN_MODE_SLEEP, FAN_MODE_PET],
    "Vital100S": [FAN_MODE_AUTO, FAN_MODE_SLEEP, FAN_MODE_PET],
}
SPEED_RANGE = {  # off is not included
    "LV-PUR131S": (1, 3),
    "Core200S": (1, 3),
    "Core300S": (1, 3),
    "Core400S": (1, 4),
    "Core600S": (1, 4),
    "EverestAir": (1, 3),
    "Vital200S": (1, 4),
    "Vital100S": (1, 4),
}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the VeSync fan platform."""

    coordinator = hass.data[DOMAIN][VS_COORDINATOR]

    @callback
    def discover(devices):
        """Add new devices to platform."""
        _setup_entities(devices, async_add_entities, coordinator)

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, VS_DISCOVERY.format(VS_DEVICES), discover)
    )

    _setup_entities(hass.data[DOMAIN][VS_DEVICES], async_add_entities, coordinator)


@callback
def _setup_entities(
    devices: list[VeSyncBaseDevice],
    async_add_entities,
    coordinator: VeSyncDataCoordinator,
):
    """Check if device is online and add entity."""
    entities = []
    for dev in devices:
        if DEV_TYPE_TO_HA.get(SKU_TO_BASE_DEVICE.get(dev.device_type, "")) == "fan":
            entities.append(VeSyncFanHA(dev, coordinator))
        else:
            _LOGGER.warning(
                "%s - Unknown device type - %s", dev.device_name, dev.device_type
            )
            continue

    async_add_entities(entities, update_before_add=True)


class VeSyncFanHA(VeSyncBaseEntity, FanEntity):
    """Representation of a VeSync fan."""

    _attr_supported_features = (
        FanEntityFeature.SET_SPEED
        | FanEntityFeature.PRESET_MODE
        | FanEntityFeature.TURN_OFF
        | FanEntityFeature.TURN_ON
    )
    _attr_name = None
    _attr_translation_key = "vesync"

    def __init__(
        self, fan: VeSyncBaseDevice, coordinator: VeSyncDataCoordinator
    ) -> None:
        """Initialize the VeSync fan device."""
        super().__init__(fan, coordinator)
        self.smartfan = fan

    @property
    def is_on(self) -> bool:
        """Return True if device is on."""
        return self.device.device_status == "on"

    @property
    def percentage(self) -> int | None:
        """Return the current speed."""
        if (
            self.smartfan.mode == "manual"
            and (current_level := self.smartfan.fan_level) is not None
        ):
            return ranged_value_to_percentage(
                SPEED_RANGE[SKU_TO_BASE_DEVICE[self.device.device_type]], current_level
            )
        return None

    @property
    def speed_count(self) -> int:
        """Return the number of speeds the fan supports."""
        return int_states_in_range(
            SPEED_RANGE[SKU_TO_BASE_DEVICE[self.device.device_type]]
        )

    @property
    def preset_modes(self) -> list[str]:
        """Get the list of available preset modes."""
        return PRESET_MODES[SKU_TO_BASE_DEVICE[self.device.device_type]]

    @property
    def preset_mode(self) -> str | None:
        """Get the current preset mode."""
        if self.smartfan.mode in (FAN_MODE_AUTO, FAN_MODE_SLEEP, FAN_MODE_TURBO):
            return self.smartfan.mode
        return None

    @property
    def unique_info(self):
        """Return the ID of this fan."""
        return self.smartfan.uuid

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the fan."""
        attr = {}

        if hasattr(self.smartfan, "active_time"):
            attr["active_time"] = self.smartfan.active_time

        if hasattr(self.smartfan, "screen_status"):
            attr["screen_status"] = self.smartfan.screen_status

        if hasattr(self.smartfan, "child_lock"):
            attr["child_lock"] = self.smartfan.child_lock

        if hasattr(self.smartfan, "night_light"):
            attr["night_light"] = self.smartfan.night_light

        if hasattr(self.smartfan, "mode"):
            attr["mode"] = self.smartfan.mode

        return attr

    def set_percentage(self, percentage: int) -> None:
        """Set the speed of the device."""
        if percentage == 0:
            self.smartfan.turn_off()
            return

        if not self.smartfan.is_on:
            self.smartfan.turn_on()

        self.smartfan.manual_mode()
        self.smartfan.change_fan_speed(
            math.ceil(
                percentage_to_ranged_value(
                    SPEED_RANGE[SKU_TO_BASE_DEVICE[self.device.device_type]], percentage
                )
            )
        )
        self.schedule_update_ha_state()

    def set_preset_mode(self, preset_mode: str) -> None:
        """Set the preset mode of device."""
        if preset_mode not in self.preset_modes:
            raise ValueError(
                f"{preset_mode} is not one of the valid preset modes: "
                f"{self.preset_modes}"
            )

        if not self.smartfan.is_on:
            self.smartfan.turn_on()

        if preset_mode == FAN_MODE_AUTO:
            self.smartfan.auto_mode()
        elif preset_mode == FAN_MODE_SLEEP:
            self.smartfan.sleep_mode()
        elif preset_mode == FAN_MODE_PET:
            self.smartfan.pet_mode()
        elif preset_mode == FAN_MODE_TURBO:
            self.smartfan.turbo_mode()

        self.schedule_update_ha_state()

    def turn_on(
        self,
        percentage: int | None = None,
        preset_mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the device on."""
        if preset_mode:
            self.set_preset_mode(preset_mode)
            return
        if percentage is None:
            percentage = 50
        self.set_percentage(percentage)

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        self.device.turn_off()
