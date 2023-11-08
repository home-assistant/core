"""Support for Logi Circle sensors."""
from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorEntityDescription,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import (
    ATTR_BATTERY_CHARGING,
    CONF_MONITORED_CONDITIONS,
    CONF_SENSORS,
    PERCENTAGE,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util.dt import as_local

from .const import ATTRIBUTION, DEVICE_BRAND, DOMAIN as LOGI_CIRCLE_DOMAIN

_LOGGER = logging.getLogger(__name__)


SENSOR_TYPES: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key="battery_level",
        native_unit_of_measurement=PERCENTAGE,
        device_class=SensorDeviceClass.BATTERY,
    ),
    SensorEntityDescription(
        key="last_activity_time",
        translation_key="last_activity",
        icon="mdi:history",
    ),
    SensorEntityDescription(
        key="recording",
        translation_key="recording_mode",
        icon="mdi:eye",
    ),
    SensorEntityDescription(
        key="signal_strength_category",
        translation_key="wifi_signal_category",
        icon="mdi:wifi",
    ),
    SensorEntityDescription(
        key="signal_strength_percentage",
        translation_key="wifi_signal_strength",
        native_unit_of_measurement=PERCENTAGE,
        icon="mdi:wifi",
    ),
    SensorEntityDescription(
        key="streaming",
        translation_key="streaming_mode",
        icon="mdi:camera",
    ),
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up a sensor for a Logi Circle device. Obsolete."""
    _LOGGER.warning("Logi Circle no longer works with sensor platform configuration")


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up a Logi Circle sensor based on a config entry."""
    devices = await hass.data[LOGI_CIRCLE_DOMAIN].cameras
    time_zone = str(hass.config.time_zone)

    monitored_conditions = entry.data[CONF_SENSORS].get(CONF_MONITORED_CONDITIONS)
    entities = [
        LogiSensor(device, time_zone, description)
        for description in SENSOR_TYPES
        if description.key in monitored_conditions
        for device in devices
        if device.supports_feature(description.key)
    ]

    async_add_entities(entities, True)


class LogiSensor(SensorEntity):
    """A sensor implementation for a Logi Circle camera."""

    _attr_attribution = ATTRIBUTION
    _attr_has_entity_name = True

    def __init__(self, camera, time_zone, description: SensorEntityDescription) -> None:
        """Initialize a sensor for Logi Circle camera."""
        self.entity_description = description
        self._camera = camera
        self._attr_unique_id = f"{camera.mac_address}-{description.key}"
        self._activity: dict[Any, Any] = {}
        self._tz = time_zone
        self._attr_device_info = DeviceInfo(
            identifiers={(LOGI_CIRCLE_DOMAIN, camera.id)},
            manufacturer=DEVICE_BRAND,
            model=camera.model_name,
            name=camera.name,
            sw_version=camera.firmware,
        )

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        state = {
            "battery_saving_mode": (
                STATE_ON if self._camera.battery_saving else STATE_OFF
            ),
            "microphone_gain": self._camera.microphone_gain,
        }

        if self.entity_description.key == "battery_level":
            state[ATTR_BATTERY_CHARGING] = self._camera.charging

        return state

    @property
    def icon(self):
        """Icon to use in the frontend, if any."""
        sensor_type = self.entity_description.key
        if sensor_type == "recording_mode" and self._attr_native_value is not None:
            return "mdi:eye" if self._attr_native_value == STATE_ON else "mdi:eye-off"
        if sensor_type == "streaming_mode" and self._attr_native_value is not None:
            return (
                "mdi:camera"
                if self._attr_native_value == STATE_ON
                else "mdi:camera-off"
            )
        return self.entity_description.icon

    async def async_update(self) -> None:
        """Get the latest data and updates the state."""
        _LOGGER.debug("Pulling data from %s sensor", self.name)
        await self._camera.update()

        if self.entity_description.key == "last_activity_time":
            last_activity = await self._camera.get_last_activity(force_refresh=True)
            if last_activity is not None:
                last_activity_time = as_local(last_activity.end_time_utc)
                self._attr_native_value = (
                    f"{last_activity_time.hour:0>2}:{last_activity_time.minute:0>2}"
                )
        else:
            state = getattr(self._camera, self.entity_description.key, None)
            if isinstance(state, bool):
                self._attr_native_value = STATE_ON if state is True else STATE_OFF
            else:
                self._attr_native_value = state
