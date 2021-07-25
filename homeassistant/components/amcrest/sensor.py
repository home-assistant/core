"""Support for Amcrest IP camera sensors."""
from __future__ import annotations

from datetime import timedelta
import logging
from typing import TYPE_CHECKING, Callable

from amcrest import AmcrestError

from homeassistant.components.sensor import SensorEntity
from homeassistant.const import CONF_NAME, CONF_SENSORS, PERCENTAGE
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import (
    ConfigType,
    DiscoveryInfoType,
    HomeAssistantType,
)

from .const import DATA_AMCREST, DEVICES, SENSOR_SCAN_INTERVAL_SECS, SERVICE_UPDATE
from .helpers import log_update_error, service_signal

if TYPE_CHECKING:
    from . import AmcrestDevice

_LOGGER = logging.getLogger(__name__)

SCAN_INTERVAL = timedelta(seconds=SENSOR_SCAN_INTERVAL_SECS)

SENSOR_PTZ_PRESET = "ptz_preset"
SENSOR_SDCARD = "sdcard"
# Sensor types are defined like: Name, units, icon
SENSORS = {
    SENSOR_PTZ_PRESET: ("PTZ Preset", None, "mdi:camera-iris"),
    SENSOR_SDCARD: ("SD Used", PERCENTAGE, "mdi:sd"),
}


async def async_setup_platform(
    hass: HomeAssistantType,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up a sensor for an Amcrest IP Camera."""
    if discovery_info is None:
        return

    name = discovery_info[CONF_NAME]
    device = hass.data[DATA_AMCREST][DEVICES][name]
    async_add_entities(
        [
            AmcrestSensor(name, device, sensor_type)
            for sensor_type in discovery_info[CONF_SENSORS]
        ],
        True,
    )


class AmcrestSensor(SensorEntity):
    """A sensor implementation for Amcrest IP camera."""

    def __init__(self, name: str, device: AmcrestDevice, sensor_type: str) -> None:
        """Initialize a sensor for Amcrest camera."""
        self._name = f"{name} {SENSORS[sensor_type][0]}"
        self._signal_name = name
        self._api = device.api
        self._sensor_type = sensor_type
        self._state: int | str | None = None
        self._attrs: dict[str, str | None] = {}
        self._unit_of_measurement: str | None = SENSORS[sensor_type][1]
        self._icon: str = SENSORS[sensor_type][2]
        self._unsub_dispatcher: Callable[[], None] | None = None

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def native_value(self) -> int | str | None:
        """Return the state of the sensor."""
        return self._state

    @property
    def extra_state_attributes(self) -> dict[str, str | None]:
        """Return the state attributes."""
        return self._attrs

    @property
    def icon(self) -> str:
        """Icon to use in the frontend, if any."""
        return self._icon

    @property
    def native_unit_of_measurement(self) -> str | None:
        """Return the units of measurement."""
        return self._unit_of_measurement

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self._api.available

    def update(self) -> None:
        """Get the latest data and updates the state."""
        if not self.available:
            return
        _LOGGER.debug("Updating %s sensor", self._name)

        try:
            if self._sensor_type == SENSOR_PTZ_PRESET:
                self._state = self._api.ptz_presets_count

            elif self._sensor_type == SENSOR_SDCARD:
                storage = self._api.storage_all
                try:
                    self._attrs[
                        "Total"
                    ] = f"{storage['total'][0]:.2f} {storage['total'][1]}"
                except ValueError:
                    self._attrs[
                        "Total"
                    ] = f"{storage['total'][0]} {storage['total'][1]}"
                try:
                    self._attrs[
                        "Used"
                    ] = f"{storage['used'][0]:.2f} {storage['used'][1]}"
                except ValueError:
                    self._attrs["Used"] = f"{storage['used'][0]} {storage['used'][1]}"
                try:
                    self._state = f"{storage['used_percent']:.2f}"
                except ValueError:
                    self._state = storage["used_percent"]
        except AmcrestError as error:
            log_update_error(_LOGGER, "update", self.name, "sensor", error)

    async def async_on_demand_update(self) -> None:
        """Update state."""
        self.async_schedule_update_ha_state(True)

    async def async_added_to_hass(self) -> None:
        """Subscribe to update signal."""
        assert self.hass is not None
        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass,
            service_signal(SERVICE_UPDATE, self._signal_name),
            self.async_on_demand_update,
        )

    async def async_will_remove_from_hass(self) -> None:
        """Disconnect from update signal."""
        assert self._unsub_dispatcher is not None
        self._unsub_dispatcher()
