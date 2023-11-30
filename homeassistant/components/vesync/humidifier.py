"""Support for VeSync humidifiers."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.humidifier import (
    HumidifierDeviceClass,
    HumidifierEntity,
    HumidifierEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common import VeSyncDevice
from .const import DOMAIN, SKU_TO_BASE_DEVICE, VS_DISCOVERY, VS_HUMIDIFIERS

_LOGGER = logging.getLogger(__name__)

DEV_TYPE_TO_HA = {
    "LUH-D301S-WEU": "humidifier",
}

HUMIDIFIER_MODE_AUTO = "auto"
HUMIDIFIER_MODE_LOW = "low"
HUMIDIFIER_MODE_HIGH = "high"

PRESET_MODES = {
    "LUH-D301S-WEU": [HUMIDIFIER_MODE_AUTO, HUMIDIFIER_MODE_LOW, HUMIDIFIER_MODE_HIGH],
}

MIST_LEVELS_MAP = {HUMIDIFIER_MODE_LOW: 1, HUMIDIFIER_MODE_HIGH: 2}


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the VeSync humidifier platform."""

    @callback
    def discover(devices):
        """Add new devices to platform."""
        _setup_entities(devices, async_add_entities)

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, VS_DISCOVERY.format(VS_HUMIDIFIERS), discover)
    )

    _setup_entities(hass.data[DOMAIN][VS_HUMIDIFIERS], async_add_entities)


@callback
def _setup_entities(devices, async_add_entities):
    """Check if device is online and add entity."""
    entities = []
    for dev in devices:
        if DEV_TYPE_TO_HA.get(SKU_TO_BASE_DEVICE.get(dev.device_type)) == "humidifier":
            entities.append(VeSyncHumidifierHA(dev))
        else:
            _LOGGER.warning(
                "%s - Unknown device type - %s", dev.device_name, dev.device_type
            )
            continue

    async_add_entities(entities, update_before_add=True)


class VeSyncHumidifierHA(VeSyncDevice, HumidifierEntity):
    """Representation of a VeSync humidifier."""

    _attr_supported_features = HumidifierEntityFeature.MODES
    _attr_name = None

    def __init__(self, humidifier) -> None:
        """Initialize the VeSync humidifier device."""
        super().__init__(humidifier)
        self.smarthumidifier = humidifier

    @property
    def device_class(self) -> HumidifierDeviceClass | None:
        """Return the device class."""
        return HumidifierDeviceClass.HUMIDIFIER

    @property
    def current_humidity(self) -> int | None:
        """Return the current humidity."""
        return self.smarthumidifier.humidity

    @property
    def target_humidity(self) -> int | None:
        """Return the humidity we try to reach."""
        return self.smarthumidifier.auto_humidity

    @property
    def mode(self) -> str | None:
        """Return the current mode, e.g., home, auto, baby.

        Requires HumidifierEntityFeature.MODES.
        """
        if self.smarthumidifier.auto_enabled:
            return HUMIDIFIER_MODE_AUTO
        return list(MIST_LEVELS_MAP.keys())[
            list(MIST_LEVELS_MAP.values()).index(self.smarthumidifier.mist_level)
        ]

    @property
    def available_modes(self) -> list[str] | None:
        """Return a list of available modes.

        Requires HumidifierEntityFeature.MODES.
        """
        return PRESET_MODES[SKU_TO_BASE_DEVICE[self.device.device_type]]

    def set_humidity(self, humidity: int) -> None:
        """Set new target humidity."""
        self.smarthumidifier.set_humidity(humidity)

    def set_mode(self, mode: str) -> None:
        """Set new mode."""
        if mode in (HUMIDIFIER_MODE_AUTO, None):
            self.smarthumidifier.set_auto_mode()
        else:
            self.smarthumidifier.set_manual_mode()
            self.smarthumidifier.set_mist_level(MIST_LEVELS_MAP[mode])

    @property
    def min_humidity(self) -> int:
        """Return the minimum humidity."""
        return 30

    @property
    def max_humidity(self) -> int:
        """Return the maximum humidity."""
        return 80

    @property
    def unique_info(self):
        """Return the ID of this humidifier."""
        return self.smarthumidifier.uuid

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the state attributes of the humidifier."""
        attr = {}

        if hasattr(self.smarthumidifier, "water_lacks"):
            attr["water_lacks"] = self.smarthumidifier.water_lacks

        if "water_tank_lifted" in self.smarthumidifier.details:
            attr["water_tank_lifted"] = self.smarthumidifier.details[
                "water_tank_lifted"
            ]

        if "display" in self.smarthumidifier.details:
            attr["display"] = self.smarthumidifier.details["display"]

        if "automatic_stop_reach_target" in self.smarthumidifier.details:
            attr["automatic_stop_reach_target"] = self.smarthumidifier.details[
                "automatic_stop_reach_target"
            ]

        return attr

    def turn_on(
        self,
        mode: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Turn the device on."""
        self.smarthumidifier.turn_on()
