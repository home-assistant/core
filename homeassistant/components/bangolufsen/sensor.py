"""Sensor entities for the Bang & Olufsen integration."""
from __future__ import annotations

from inflection import titleize, underscore
from mozart_api.models import BatteryState, PlaybackContentMetadata

from homeassistant.components.sensor import (
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN, BangOlufsenEntity, EntityEnum, WebSocketNotification


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Sensor entities from config entry."""
    entities = []

    # Add Sensor entities.
    for sensor in hass.data[DOMAIN][config_entry.unique_id][EntityEnum.SENSORS]:
        entities.append(sensor)

    async_add_entities(new_entities=entities)


class BangOlufsenSensor(BangOlufsenEntity, SensorEntity):
    """Base Sensor class."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Init the Sensor."""
        super().__init__(entry)

        self._attr_state_class = SensorStateClass.MEASUREMENT


class BangOlufsenSensorBatteryLevel(BangOlufsenSensor):
    """Battery level Sensor."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Init the battery level Sensor."""
        super().__init__(entry)

        self._attr_name = f"{self._name} Battery level"
        self._attr_unique_id = f"{self._unique_id}-battery-level"
        self._attr_device_class = SensorDeviceClass.BATTERY
        self._attr_native_unit_of_measurement = "%"
        self._attr_icon = "mdi:battery"

    async def async_added_to_hass(self) -> None:
        """Turn on the dispatchers."""
        await super().async_added_to_hass()

        self._dispatchers.append(
            async_dispatcher_connect(
                self.hass,
                f"{self._unique_id}_{WebSocketNotification.BATTERY}",
                self._update_battery,
            )
        )

    async def _update_battery(self, data: BatteryState) -> None:
        """Update sensor value."""
        self._attr_native_value = data.battery_level
        self.async_write_ha_state()


class BangOlufsenSensorBatteryChargingTime(BangOlufsenSensor):
    """Battery charging time Sensor."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Init the battery charging time Sensor."""
        super().__init__(entry)

        self._attr_name = f"{self._name} Battery charging time"
        self._attr_unique_id = f"{self._unique_id}-battery-charging-time"
        self._attr_device_class = SensorDeviceClass.DURATION
        self._attr_native_unit_of_measurement = "min"
        self._attr_icon = "mdi:battery-arrow-up"
        self._attr_entity_registry_enabled_default = False

    async def async_added_to_hass(self) -> None:
        """Turn on the dispatchers."""
        await super().async_added_to_hass()

        self._dispatchers.append(
            async_dispatcher_connect(
                self.hass,
                f"{self._unique_id}_{WebSocketNotification.BATTERY}",
                self._update_battery,
            )
        )

    async def _update_battery(self, data: BatteryState) -> None:
        """Update sensor value."""

        self._attr_available = True

        charging_time = data.remaining_charging_time_minutes

        # The charging time is 65535 if the device is not charging.
        if charging_time == 65535:
            self._attr_native_value = 0

        else:
            self._attr_native_value = charging_time

        self.async_write_ha_state()


class BangOlufsenSensorBatteryPlayingTime(BangOlufsenSensor):
    """Battery playing time Sensor."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Init the battery playing time Sensor."""
        super().__init__(entry)

        self._attr_name = f"{self._name} Battery playing time"
        self._attr_unique_id = f"{self._unique_id}-battery-playing-time"
        self._attr_native_unit_of_measurement = "min"
        self._attr_icon = "mdi:battery-arrow-down"
        self._attr_entity_registry_enabled_default = False

    async def async_added_to_hass(self) -> None:
        """Turn on the dispatchers."""
        await super().async_added_to_hass()

        self._dispatchers.append(
            async_dispatcher_connect(
                self.hass,
                f"{self._unique_id}_{WebSocketNotification.BATTERY}",
                self._update_battery,
            )
        )

    async def _update_battery(self, data: PlaybackContentMetadata) -> None:
        """Update sensor value."""
        self._attr_available = True

        playing_time = data.remaining_playing_time_minutes

        # The playing time is 65535 if the device is charging
        if playing_time == 65535:
            self._attr_native_value = 0

        else:
            self._attr_native_value = playing_time

        self.async_write_ha_state()


class BangOlufsenSensorMediaId(BangOlufsenSensor):
    """Media id Sensor."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Init the media id Sensor."""
        super().__init__(entry)

        self._attr_name = f"{self._name} Media Id"
        self._attr_unique_id = f"{self._unique_id}-media-id"
        self._attr_icon = "mdi:information"
        self._attr_device_class = None
        self._attr_state_class = None
        self._attr_entity_registry_enabled_default = False

        self._attr_native_value = None

    async def async_added_to_hass(self) -> None:
        """Turn on the dispatchers."""
        await super().async_added_to_hass()

        self._dispatchers.append(
            async_dispatcher_connect(
                self.hass,
                f"{self.entry.unique_id}_{WebSocketNotification.PLAYBACK_METADATA}",
                self._update_playback_metadata,
            ),
        )

    async def _update_playback_metadata(self, data: PlaybackContentMetadata) -> None:
        """Update Sensor value."""
        self._attr_native_value = data.source_internal_id
        self.async_write_ha_state()


class BangOlufsenSensorInputSignal(BangOlufsenSensor):
    """Input signal Sensor."""

    def __init__(self, entry: ConfigEntry) -> None:
        """Init the input signal Sensor."""
        super().__init__(entry)

        self._attr_name = f"{self._name} Input signal"
        self._attr_unique_id = f"{self._unique_id}-input-signal"
        self._attr_device_class = None
        self._attr_state_class = None
        self._attr_icon = "mdi:audio-input-stereo-minijack"
        self._attr_entity_registry_enabled_default = False

    async def async_added_to_hass(self) -> None:
        """Turn on the dispatchers."""
        await super().async_added_to_hass()

        self._dispatchers.append(
            async_dispatcher_connect(
                self.hass,
                f"{self._unique_id}_{WebSocketNotification.PLAYBACK_METADATA}",
                self._update_playback_metadata,
            )
        )

    async def _update_playback_metadata(self, data: PlaybackContentMetadata) -> None:
        """Update Sensor value."""
        if data.encoding:
            # Ensure that abbreviated formats are capitialized and non-abbreviated formats are made "human readable"
            encoding = titleize(underscore(data.encoding))
            if data.encoding.capitalize() == encoding:
                encoding = data.encoding.upper()

            input_channel_processing = None
            if data.input_channel_processing:
                input_channel_processing = titleize(
                    underscore(data.input_channel_processing)
                )

            self._attr_native_value = f"{encoding}{f' - {input_channel_processing}' if input_channel_processing else ''}{f' - {data.input_channels}' if data.input_channels else ''}"
        else:
            self._attr_native_value = None

        self.async_write_ha_state()
