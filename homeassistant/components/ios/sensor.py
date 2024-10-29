"""Support for Home Assistant iOS app sensors."""

from __future__ import annotations

from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.icon import icon_for_battery_level
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from . import devices
from .const import (
    ATTR_BATTERY,
    ATTR_BATTERY_LEVEL,
    ATTR_BATTERY_STATE,
    ATTR_BATTERY_STATE_FULL,
    ATTR_BATTERY_STATE_UNKNOWN,
    ATTR_BATTERY_STATE_UNPLUGGED,
    ATTR_DEVICE,
    ATTR_DEVICE_ID,
    ATTR_DEVICE_NAME,
    ATTR_DEVICE_PERMANENT_ID,
    ATTR_DEVICE_SYSTEM_VERSION,
    ATTR_DEVICE_TYPE,
    DOMAIN,
)

SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
    ),
    SensorEntityDescription(
        key="state",
        translation_key="battery_state",
    ),
)

DEFAULT_ICON_LEVEL = "mdi:battery"
DEFAULT_ICON_STATE = "mdi:power-plug"


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the iOS sensor."""
    # Leave here for if someone accidentally adds platform: ios to config


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up iOS from a config entry."""
    async_add_entities(
        IOSSensor(device_name, device, description)
        for device_name, device in devices(hass).items()
        for description in SENSOR_TYPES
    )


class IOSSensor(SensorEntity):
    """Representation of an iOS sensor."""

    _attr_should_poll = False
    _attr_has_entity_name = True

    def __init__(
        self,
        device_name: str,
        device: dict[str, Any],
        description: SensorEntityDescription,
    ) -> None:
        """Initialize the sensor."""
        self.entity_description = description
        self._device = device

        device_id = device[ATTR_DEVICE_ID]
        self._attr_unique_id = f"{description.key}_{device_id}"

    @property
    def device_info(self) -> DeviceInfo:
        """Return information about the device."""
        return DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    self._device[ATTR_DEVICE][ATTR_DEVICE_PERMANENT_ID],
                )
            },
            manufacturer="Apple",
            model=self._device[ATTR_DEVICE][ATTR_DEVICE_TYPE],
            name=self._device[ATTR_DEVICE][ATTR_DEVICE_NAME],
            sw_version=self._device[ATTR_DEVICE][ATTR_DEVICE_SYSTEM_VERSION],
        )

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return the device state attributes."""
        device = self._device[ATTR_DEVICE]
        device_battery = self._device[ATTR_BATTERY]
        return {
            "Battery State": device_battery[ATTR_BATTERY_STATE],
            "Battery Level": device_battery[ATTR_BATTERY_LEVEL],
            "Device Type": device[ATTR_DEVICE_TYPE],
            "Device Name": device[ATTR_DEVICE_NAME],
            "Device Version": device[ATTR_DEVICE_SYSTEM_VERSION],
        }

    @property
    def icon(self) -> str:
        """Return the icon to use in the frontend, if any."""
        device_battery = self._device[ATTR_BATTERY]
        battery_state = device_battery[ATTR_BATTERY_STATE]
        battery_level = device_battery[ATTR_BATTERY_LEVEL]
        charging = True
        icon_state = DEFAULT_ICON_STATE
        if battery_state in (
            ATTR_BATTERY_STATE_FULL,
            ATTR_BATTERY_STATE_UNPLUGGED,
        ):
            charging = False
            icon_state = f"{DEFAULT_ICON_STATE}-off"
        elif battery_state == ATTR_BATTERY_STATE_UNKNOWN:
            battery_level = None
            charging = False
            icon_state = f"{DEFAULT_ICON_LEVEL}-unknown"

        if self.entity_description.key == "state":
            return icon_state
        return icon_for_battery_level(battery_level=battery_level, charging=charging)

    @callback
    def _update(self, device: dict[str, Any]) -> None:
        """Get the latest state of the sensor."""
        self._device = device
        self._attr_native_value = self._device[ATTR_BATTERY][
            self.entity_description.key
        ]
        self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Handle addition to hass: register to dispatch."""
        self._attr_native_value = self._device[ATTR_BATTERY][
            self.entity_description.key
        ]
        device_id = self._device[ATTR_DEVICE_ID]
        self.async_on_remove(
            async_dispatcher_connect(self.hass, f"{DOMAIN}.{device_id}", self._update)
        )
