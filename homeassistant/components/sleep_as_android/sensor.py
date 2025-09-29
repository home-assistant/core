"""Sensor platform for Sleep as Android integration."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from homeassistant.components.sensor import (
    RestoreSensor,
    SensorDeviceClass,
    SensorEntityDescription,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.util import dt as dt_util

from . import SleepAsAndroidConfigEntry
from .const import ALARM_LABEL_DEFAULT, ATTR_EVENT, ATTR_VALUE1, ATTR_VALUE2
from .entity import SleepAsAndroidEntity

PARALLEL_UPDATES = 0


class SleepAsAndroidSensor(StrEnum):
    """Sleep as Android sensors."""

    NEXT_ALARM = "next_alarm"
    ALARM_LABEL = "alarm_label"


SENSOR_DESCRIPTIONS: tuple[SensorEntityDescription, ...] = (
    SensorEntityDescription(
        key=SleepAsAndroidSensor.NEXT_ALARM,
        translation_key=SleepAsAndroidSensor.NEXT_ALARM,
        device_class=SensorDeviceClass.TIMESTAMP,
    ),
    SensorEntityDescription(
        key=SleepAsAndroidSensor.ALARM_LABEL,
        translation_key=SleepAsAndroidSensor.ALARM_LABEL,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: SleepAsAndroidConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up the sensor platform."""

    async_add_entities(
        SleepAsAndroidSensorEntity(config_entry, description)
        for description in SENSOR_DESCRIPTIONS
    )


class SleepAsAndroidSensorEntity(SleepAsAndroidEntity, RestoreSensor):
    """A sensor entity."""

    entity_description: SensorEntityDescription

    @callback
    def _async_handle_event(self, webhook_id: str, data: dict[str, str]) -> None:
        """Handle the Sleep as Android event."""

        if webhook_id == self.webhook_id and data[ATTR_EVENT] in (
            "alarm_snooze_clicked",
            "alarm_snooze_canceled",
            "alarm_alert_start",
            "alarm_alert_dismiss",
            "alarm_skip_next",
            "show_skip_next_alarm",
            "alarm_rescheduled",
        ):
            if (
                self.entity_description.key is SleepAsAndroidSensor.NEXT_ALARM
                and (alarm_time := data.get(ATTR_VALUE1))
                and alarm_time.isnumeric()
            ):
                self._attr_native_value = datetime.fromtimestamp(
                    int(alarm_time) / 1000, tz=dt_util.get_default_time_zone()
                )
            if self.entity_description.key is SleepAsAndroidSensor.ALARM_LABEL and (
                label := data.get(ATTR_VALUE2, ALARM_LABEL_DEFAULT)
            ):
                self._attr_native_value = label

            self.async_write_ha_state()

    async def async_added_to_hass(self) -> None:
        """Restore entity state."""
        state = await self.async_get_last_sensor_data()
        if state:
            self._attr_native_value = state.native_value

        await super().async_added_to_hass()
