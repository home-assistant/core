"""Support for VeSync humidifiers."""
from collections.abc import Mapping
from dataclasses import dataclass
import logging
from typing import Any

from pyvesync.vesyncfan import VeSyncHumid200S, VeSyncHumid200300S

from homeassistant.components.humidifier import (
    MODE_AUTO,
    MODE_NORMAL,
    MODE_SLEEP,
    HumidifierDeviceClass,
    HumidifierEntity,
    HumidifierEntityDescription,
    HumidifierEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .common import DEVICE_HELPER, VeSyncDevice
from .const import DOMAIN, VS_DISCOVERY, VS_HUMIDIFIERS

_LOGGER = logging.getLogger(__name__)

MAX_HUMIDITY = 80
MIN_HUMIDITY = 30

PRESET_MODES = {
    "Classic200S": [MODE_NORMAL, MODE_AUTO],
    "Classic300S": [MODE_NORMAL, MODE_AUTO, MODE_SLEEP],
    "Dual200S": [MODE_NORMAL, MODE_AUTO],
    "LV600S": [MODE_NORMAL, MODE_AUTO, MODE_SLEEP],
    "OASISMIST": [MODE_NORMAL, MODE_AUTO, MODE_SLEEP],
}

MODE_MAP = {
    "normal": MODE_NORMAL,
    "manual": MODE_NORMAL,
    "humidity": MODE_AUTO,
    "auto": MODE_AUTO,
    "sleep": MODE_SLEEP,
}


@dataclass
class VeSyncHumidifierEntityDescription(HumidifierEntityDescription):
    """Describe VeSync humidifier entity."""

    def __init__(self) -> None:
        """Initialize the VeSync humidifier entity description."""
        super().__init__(key="humidifier")
        self.icon = "mdi:air-humidifier"
        self.device_class = HumidifierDeviceClass.HUMIDIFIER


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the VeSync humidifier platform."""

    @callback
    def discover(devices: list):
        """Add new devices to platform."""
        entities = []
        for dev in devices:
            if DEVICE_HELPER.is_humidifier(dev.device_type):
                entities.append(
                    VeSyncHumidifierHA(dev, VeSyncHumidifierEntityDescription())
                )
            else:
                _LOGGER.warning(
                    "%s - Unknown device type - %s", dev.device_name, dev.device_type
                )
                continue

        async_add_entities(entities, update_before_add=True)

    discover(hass.data[DOMAIN][VS_HUMIDIFIERS])

    config_entry.async_on_unload(
        async_dispatcher_connect(hass, VS_DISCOVERY.format(VS_HUMIDIFIERS), discover)
    )


class VeSyncHumidifierHA(VeSyncDevice, HumidifierEntity):
    """Representation of a VeSync humidifier."""

    device: VeSyncHumid200300S | VeSyncHumid200S
    entity_description: VeSyncHumidifierEntityDescription

    def __init__(
        self, humidifier, description: VeSyncHumidifierEntityDescription
    ) -> None:
        """Initialize the VeSync humidifier device."""
        super().__init__(humidifier)
        self.entity_description = description

        if image := humidifier.device_image:
            self._attr_entity_picture = image

        # From pyvesync set_humidity validation
        self._attr_min_humidity = MIN_HUMIDITY
        self._attr_max_humidity = MAX_HUMIDITY

        if mode := MODE_MAP[humidifier.details["mode"]]:
            self._attr_mode = mode

        if mist_modes := humidifier.config_dict["mist_modes"]:
            self._attr_available_modes = [MODE_MAP[mmode] for mmode in mist_modes]

        self._attr_supported_features = HumidifierEntityFeature(0)
        if mode is not None:
            self._attr_supported_features |= HumidifierEntityFeature.MODES

    @property
    def unique_info(self):
        """Return the ID of this humidifier."""
        return self.device.uuid

    @property
    def extra_state_attributes(self) -> Mapping[str, Any] | None:
        """Return the state attributes of the fan."""
        extra_attr = {}

        if hasattr(self.device, "warm_mist_feature"):
            extra_attr["warm_mist_feature"] = self.device.warm_mist_feature

        return extra_attr

    @property
    def is_on(self) -> bool:
        """Return True if humidifier is on."""
        return self.device.is_on

    def turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        self.device.turn_on()
        self.schedule_update_ha_state()

    @property
    def mode(self) -> str | None:
        """Get the current preset mode."""
        mmode = MODE_MAP[self.device.details["mode"]]
        if self.available_modes and mmode in self.available_modes:
            return mmode
        return None

    def set_mode(self, mode: str) -> None:
        """Set the preset mode of device."""
        if not self.available_modes:
            raise ValueError("No available modes were specified")
        if mode is None or mode not in self.available_modes:
            raise ValueError(
                f"{mode} is not one of the available modes: {self.available_modes}"
            )

        if not self.device.is_on:
            self.device.turn_on()

        self._attr_mode = MODE_MAP[mode]
        if self._attr_mode == MODE_NORMAL:
            self.device.set_manual_mode()
        elif self._attr_mode == MODE_SLEEP:
            self.device.set_humidity_mode(MODE_SLEEP)
        elif self._attr_mode == MODE_AUTO:
            self.device.set_auto_mode()

        self.schedule_update_ha_state()

    @property
    def target_humidity(self) -> int | None:
        """Return the current target humidity."""
        return self.device.auto_humidity

    def set_humidity(self, humidity: int) -> None:
        """Set the humidity of device."""
        if humidity not in range(self.min_humidity, self.max_humidity + 1):
            raise ValueError(
                "{humidity} is not between {self.min_humidity} and {self.max_humidity} (inclusive)"
            )

        if not self.device.is_on:
            self.device.turn_on()

        self.device.set_humidity(humidity)
        self.schedule_update_ha_state()
