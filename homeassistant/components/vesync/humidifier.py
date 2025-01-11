"""Support for VeSync humidifiers."""

import logging
from typing import Any

from pyvesync.vesyncbasedevice import VeSyncBaseDevice

from homeassistant.components.humidifier import (
    ATTR_HUMIDITY,
    MODE_AUTO,
    MODE_NORMAL,
    MODE_SLEEP,
    HumidifierEntity,
    HumidifierEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common import is_humidifier
from .const import (
    DOMAIN,
    VS_COORDINATOR,
    VS_DEVICES,
    VS_DISCOVERY,
    VS_HUMIDIFIER_MODE_AUTO,
    VS_HUMIDIFIER_MODE_HUMIDITY,
    VS_HUMIDIFIER_MODE_MANUAL,
    VS_HUMIDIFIER_MODE_SLEEP,
    VeSyncHumidifierDevice,
)
from .coordinator import VeSyncDataCoordinator
from .entity import VeSyncBaseEntity

_LOGGER = logging.getLogger(__name__)


MIN_HUMIDITY = 30
MAX_HUMIDITY = 80

VS_TO_HA_ATTRIBUTES = {ATTR_HUMIDITY: "current_humidity"}

VS_TO_HA_MODE_MAP = {
    VS_HUMIDIFIER_MODE_AUTO: MODE_AUTO,
    VS_HUMIDIFIER_MODE_HUMIDITY: MODE_AUTO,
    VS_HUMIDIFIER_MODE_MANUAL: MODE_NORMAL,
    VS_HUMIDIFIER_MODE_SLEEP: MODE_SLEEP,
}

HA_TO_VS_MODE_MAP = {v: k for k, v in VS_TO_HA_MODE_MAP.items()}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the VeSync humidifier platform."""

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
    async_add_entities: AddEntitiesCallback,
    coordinator: VeSyncDataCoordinator,
):
    """Add humidifier entities."""
    async_add_entities(
        VeSyncHumidifierHA(dev, coordinator) for dev in devices if is_humidifier(dev)
    )


def _get_ha_mode(vs_mode: str) -> str | None:
    ha_mode = VS_TO_HA_MODE_MAP.get(vs_mode)
    if ha_mode is None:
        _LOGGER.warning("Unknown mode '%s'", vs_mode)
    return ha_mode


def _get_vs_mode(ha_mode: str) -> str | None:
    return HA_TO_VS_MODE_MAP.get(ha_mode)


class VeSyncHumidifierHA(VeSyncBaseEntity, HumidifierEntity):
    """Representation of a VeSync humidifier."""

    # The base VeSyncBaseEntity has _attr_has_entity_name and this is to follow the device name
    _attr_name = None

    _attr_max_humidity = MAX_HUMIDITY
    _attr_min_humidity = MIN_HUMIDITY
    _attr_supported_features = HumidifierEntityFeature.MODES

    device: VeSyncHumidifierDevice

    @property
    def available_modes(self) -> list[str]:
        """Return the available mist modes."""
        return [
            ha_mode
            for ha_mode in (_get_ha_mode(vs_mode) for vs_mode in self.device.mist_modes)
            if ha_mode
        ]

    @property
    def target_humidity(self) -> int:
        """Return the humidity we try to reach."""
        return self.device.config["auto_target_humidity"]

    @property
    def mode(self) -> str | None:
        """Get the current preset mode."""
        return _get_ha_mode(self.device.details["mode"])

    def set_humidity(self, humidity: int) -> None:
        """Set the target humidity of the device."""
        if not self.device.set_humidity(humidity):
            raise HomeAssistantError(
                f"An error occurred while setting humidity {humidity}."
            )

    def set_mode(self, mode: str) -> None:
        """Set the mode of the device."""
        if mode not in self.available_modes:
            raise HomeAssistantError(
                "{mode} is not one of the valid available modes: {self.available_modes}"
            )
        if not self.device.set_humidity_mode(_get_vs_mode(mode)):
            raise HomeAssistantError(f"An error occurred while setting mode {mode}.")

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        success = self.device.turn_on()
        if not success:
            raise HomeAssistantError("An error occurred while turning on.")

    def turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        success = self.device.turn_off()
        if not success:
            raise HomeAssistantError("An error occurred while turning off.")

    @property
    def is_on(self) -> bool:
        """Return True if device is on."""
        return self.device.device_status == "on"
