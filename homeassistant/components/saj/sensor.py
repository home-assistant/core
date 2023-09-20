"""SAJ solar inverter interface."""
from __future__ import annotations

from collections.abc import Callable, Coroutine
from datetime import date, datetime
import logging
from typing import Any

import pysaj
import voluptuous as vol

from homeassistant.components.sensor import (
    PLATFORM_SCHEMA,
    SensorDeviceClass,
    SensorEntity,
    SensorStateClass,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PASSWORD,
    CONF_TYPE,
    CONF_USERNAME,
    EVENT_HOMEASSISTANT_STOP,
    UnitOfEnergy,
    UnitOfMass,
    UnitOfPower,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import CALLBACK_TYPE, HomeAssistant, callback
from homeassistant.exceptions import PlatformNotReady
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_call_later
from homeassistant.helpers.start import async_at_start
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

_LOGGER = logging.getLogger(__name__)

MIN_INTERVAL = 5
MAX_INTERVAL = 300

INVERTER_TYPES = ["ethernet", "wifi"]

SAJ_UNIT_MAPPINGS = {
    "": None,
    "h": UnitOfTime.HOURS,
    "kg": UnitOfMass.KILOGRAMS,
    "kWh": UnitOfEnergy.KILO_WATT_HOUR,
    "W": UnitOfPower.WATT,
    "°C": UnitOfTemperature.CELSIUS,
}

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Required(CONF_HOST): cv.string,
        vol.Optional(CONF_NAME): cv.string,
        vol.Optional(CONF_TYPE, default=INVERTER_TYPES[0]): vol.In(INVERTER_TYPES),
        vol.Inclusive(CONF_USERNAME, "credentials"): cv.string,
        vol.Inclusive(CONF_PASSWORD, "credentials"): cv.string,
    }
)


async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
    """Set up the SAJ sensors."""

    remove_interval_update = None
    wifi = config[CONF_TYPE] == INVERTER_TYPES[1]

    # Init all sensors
    sensor_def = pysaj.Sensors(wifi)

    # Use all sensors by default
    hass_sensors = []

    kwargs = {}
    if wifi:
        kwargs["wifi"] = True
        if config.get(CONF_USERNAME) and config.get(CONF_PASSWORD):
            kwargs["username"] = config[CONF_USERNAME]
            kwargs["password"] = config[CONF_PASSWORD]

    try:
        saj = pysaj.SAJ(config[CONF_HOST], **kwargs)
        done = await saj.read(sensor_def)
    except pysaj.UnauthorizedException:
        _LOGGER.error("Username and/or password is wrong")
        return
    except pysaj.UnexpectedResponseException as err:
        _LOGGER.error(
            "Error in SAJ, please check host/ip address. Original error: %s", err
        )
        return

    if not done:
        raise PlatformNotReady

    for sensor in sensor_def:
        if sensor.enabled:
            hass_sensors.append(
                SAJsensor(saj.serialnumber, sensor, inverter_name=config.get(CONF_NAME))
            )

    async_add_entities(hass_sensors)

    async def async_saj() -> bool:
        """Update all the SAJ sensors."""
        success = await saj.read(sensor_def)

        for sensor in hass_sensors:
            state_unknown = False
            # SAJ inverters are powered by DC via solar panels and thus are
            # offline after the sun has set. If a sensor resets on a daily
            # basis like "today_yield", this reset won't happen automatically.
            # Code below checks if today > day when sensor was last updated
            # and if so: set state to None.
            # Sensors with live values like "temperature" or "current_power"
            # will also be reset to None.
            if not success and (
                (sensor.per_day_basis and date.today() > sensor.date_updated)
                or (not sensor.per_day_basis and not sensor.per_total_basis)
            ):
                state_unknown = True
            sensor.async_update_values(unknown_state=state_unknown)

        return success

    @callback
    def start_update_interval(hass: HomeAssistant) -> None:
        """Start the update interval scheduling."""
        nonlocal remove_interval_update
        remove_interval_update = async_track_time_interval_backoff(hass, async_saj)

    @callback
    def stop_update_interval(event):
        """Properly cancel the scheduled update."""
        remove_interval_update()

    hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, stop_update_interval)
    async_at_start(hass, start_update_interval)


@callback
def async_track_time_interval_backoff(
    hass: HomeAssistant, action: Callable[[], Coroutine[Any, Any, bool]]
) -> CALLBACK_TYPE:
    """Add a listener that fires repetitively and increases the interval when failed."""
    remove = None
    interval = MIN_INTERVAL

    async def interval_listener(now: datetime | None = None) -> None:
        """Handle elapsed interval with backoff."""
        nonlocal interval, remove
        try:
            if await action():
                interval = MIN_INTERVAL
            else:
                interval = min(interval * 2, MAX_INTERVAL)
        finally:
            remove = async_call_later(hass, interval, interval_listener)

    hass.async_create_task(interval_listener())

    def remove_listener() -> None:
        """Remove interval listener."""
        if remove:
            remove()

    return remove_listener


class SAJsensor(SensorEntity):
    """Representation of a SAJ sensor."""

    _attr_should_poll = False

    def __init__(
        self,
        serialnumber: str | None,
        pysaj_sensor: pysaj.Sensor,
        inverter_name: str | None = None,
    ) -> None:
        """Initialize the SAJ sensor."""
        self._sensor = pysaj_sensor
        self._inverter_name = inverter_name
        self._serialnumber = serialnumber
        self._state = self._sensor.value

        if pysaj_sensor.name in ("current_power", "temperature"):
            self._attr_state_class = SensorStateClass.MEASUREMENT
        if pysaj_sensor.name == "total_yield":
            self._attr_state_class = SensorStateClass.TOTAL_INCREASING

        self._attr_unique_id = f"{serialnumber}_{pysaj_sensor.name}"
        native_uom = SAJ_UNIT_MAPPINGS[pysaj_sensor.unit]
        self._attr_native_unit_of_measurement = native_uom
        if self._inverter_name:
            self._attr_name = f"saj_{self._inverter_name}_{pysaj_sensor.name}"
        else:
            self._attr_name = f"saj_{pysaj_sensor.name}"
        if native_uom == UnitOfPower.WATT:
            self._attr_device_class = SensorDeviceClass.POWER
        if native_uom == UnitOfEnergy.KILO_WATT_HOUR:
            self._attr_device_class = SensorDeviceClass.ENERGY
        if native_uom in (
            UnitOfTemperature.CELSIUS,
            UnitOfTemperature.FAHRENHEIT,
        ):
            self._attr_device_class = SensorDeviceClass.TEMPERATURE

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def per_day_basis(self) -> bool:
        """Return if the sensors value is on daily basis or not."""
        return self._sensor.per_day_basis

    @property
    def per_total_basis(self) -> bool:
        """Return if the sensors value is cumulative or not."""
        return self._sensor.per_total_basis

    @property
    def date_updated(self) -> date:
        """Return the date when the sensor was last updated."""
        return self._sensor.date

    @callback
    def async_update_values(self, unknown_state=False):
        """Update this sensor."""
        update = False

        if self._sensor.value != self._state:
            update = True
            self._state = self._sensor.value

        if unknown_state and self._state is not None:
            update = True
            self._state = None

        if update:
            self.async_write_ha_state()
