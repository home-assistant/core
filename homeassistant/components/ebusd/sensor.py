"""Support for Ebusd sensors."""

from __future__ import annotations

import datetime
import logging
from typing import Any, cast

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle, dt as dt_util

from . import EbusdData
from .const import EBUSD_DATA, SensorSpecs

TIME_FRAME1_BEGIN = "time_frame1_begin"
TIME_FRAME1_END = "time_frame1_end"
TIME_FRAME2_BEGIN = "time_frame2_begin"
TIME_FRAME2_END = "time_frame2_end"
TIME_FRAME3_BEGIN = "time_frame3_begin"
TIME_FRAME3_END = "time_frame3_end"
MIN_TIME_BETWEEN_UPDATES = datetime.timedelta(seconds=15)

_LOGGER = logging.getLogger(__name__)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the Ebus sensor."""
    if not discovery_info:
        return
    ebusd_api = hass.data[EBUSD_DATA]
    monitored_conditions: list[str] = discovery_info["monitored_conditions"]
    name: str = discovery_info["client_name"]

    add_entities(
        (
            EbusdSensor(ebusd_api, discovery_info["sensor_types"][condition], name)
            for condition in monitored_conditions
        ),
        True,
    )


class EbusdSensor(SensorEntity):
    """Ebusd component sensor methods definition."""

    def __init__(self, data: EbusdData, sensor: SensorSpecs, name: str) -> None:
        """Initialize the sensor."""
        self._client_name = name
        (
            self._name,
            self._unit_of_measurement,
            self._icon,
            self._type,
            self._device_class,
        ) = sensor
        self.data = data

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return f"{self._client_name} {self._name}"

    @property
    def extra_state_attributes(self) -> dict[str, Any] | None:
        """Return the device state attributes."""
        if self._type == 1 and (native_value := self.native_value) is not None:
            schedule: dict[str, str | None] = {
                TIME_FRAME1_BEGIN: None,
                TIME_FRAME1_END: None,
                TIME_FRAME2_BEGIN: None,
                TIME_FRAME2_END: None,
                TIME_FRAME3_BEGIN: None,
                TIME_FRAME3_END: None,
            }
            time_frame = cast(str, native_value).split(";")
            for index, item in enumerate(sorted(schedule.items())):
                if index < len(time_frame):
                    parsed = datetime.datetime.strptime(time_frame[index], "%H:%M")
                    parsed = parsed.replace(
                        dt_util.now().year, dt_util.now().month, dt_util.now().day
                    )
                    schedule[item[0]] = parsed.isoformat()
            return schedule
        return None

    @property
    def device_class(self) -> SensorDeviceClass | None:
        """Return the class of this device, from component DEVICE_CLASSES."""
        return self._device_class

    @property
    def icon(self) -> str | None:
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self) -> None:
        """Fetch new state data for the sensor."""
        try:
            self.data.update(self._name, self._type)
            if self._name not in self.data.value:
                return

            self._attr_native_value = self.data.value[self._name]
        except RuntimeError:
            _LOGGER.debug("EbusdData.update exception")
