"""Support for Vallox ventilation unit sensors."""

from datetime import datetime, timedelta
import logging

from homeassistant.const import (
    DEVICE_CLASS_HUMIDITY,
    DEVICE_CLASS_TEMPERATURE,
    DEVICE_CLASS_TIMESTAMP,
    TEMP_CELSIUS,
    UNIT_PERCENTAGE,
)
from homeassistant.core import callback
from homeassistant.helpers.dispatcher import async_dispatcher_connect
from homeassistant.helpers.entity import Entity

from . import DOMAIN, METRIC_KEY_MODE, SIGNAL_VALLOX_STATE_UPDATE

_LOGGER = logging.getLogger(__name__)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the sensors."""
    if discovery_info is None:
        return

    name = hass.data[DOMAIN]["name"]
    state_proxy = hass.data[DOMAIN]["state_proxy"]

    sensors = [
        ValloxProfileSensor(
            name=f"{name} Current Profile",
            state_proxy=state_proxy,
            device_class=None,
            unit_of_measurement=None,
            icon="mdi:gauge",
        ),
        ValloxFanSpeedSensor(
            name=f"{name} Fan Speed",
            state_proxy=state_proxy,
            metric_key="A_CYC_FAN_SPEED",
            device_class=None,
            unit_of_measurement=UNIT_PERCENTAGE,
            icon="mdi:fan",
        ),
        ValloxSensor(
            name=f"{name} Extract Air",
            state_proxy=state_proxy,
            metric_key="A_CYC_TEMP_EXTRACT_AIR",
            device_class=DEVICE_CLASS_TEMPERATURE,
            unit_of_measurement=TEMP_CELSIUS,
            icon=None,
        ),
        ValloxSensor(
            name=f"{name} Exhaust Air",
            state_proxy=state_proxy,
            metric_key="A_CYC_TEMP_EXHAUST_AIR",
            device_class=DEVICE_CLASS_TEMPERATURE,
            unit_of_measurement=TEMP_CELSIUS,
            icon=None,
        ),
        ValloxSensor(
            name=f"{name} Outdoor Air",
            state_proxy=state_proxy,
            metric_key="A_CYC_TEMP_OUTDOOR_AIR",
            device_class=DEVICE_CLASS_TEMPERATURE,
            unit_of_measurement=TEMP_CELSIUS,
            icon=None,
        ),
        ValloxSensor(
            name=f"{name} Supply Air",
            state_proxy=state_proxy,
            metric_key="A_CYC_TEMP_SUPPLY_AIR",
            device_class=DEVICE_CLASS_TEMPERATURE,
            unit_of_measurement=TEMP_CELSIUS,
            icon=None,
        ),
        ValloxSensor(
            name=f"{name} Humidity",
            state_proxy=state_proxy,
            metric_key="A_CYC_RH_VALUE",
            device_class=DEVICE_CLASS_HUMIDITY,
            unit_of_measurement=UNIT_PERCENTAGE,
            icon=None,
        ),
        ValloxFilterRemainingSensor(
            name=f"{name} Remaining Time For Filter",
            state_proxy=state_proxy,
            metric_key="A_CYC_REMAINING_TIME_FOR_FILTER",
            device_class=DEVICE_CLASS_TIMESTAMP,
            unit_of_measurement=None,
            icon="mdi:filter",
        ),
    ]

    async_add_entities(sensors, update_before_add=False)


class ValloxSensor(Entity):
    """Representation of a Vallox sensor."""

    def __init__(
        self, name, state_proxy, metric_key, device_class, unit_of_measurement, icon
    ) -> None:
        """Initialize the Vallox sensor."""
        self._name = name
        self._state_proxy = state_proxy
        self._metric_key = metric_key
        self._device_class = device_class
        self._unit_of_measurement = unit_of_measurement
        self._icon = icon
        self._available = None
        self._state = None

    @property
    def should_poll(self):
        """Do not poll the device."""
        return False

    @property
    def name(self):
        """Return the name."""
        return self._name

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return self._unit_of_measurement

    @property
    def device_class(self):
        """Return the device class."""
        return self._device_class

    @property
    def icon(self):
        """Return the icon."""
        return self._icon

    @property
    def available(self):
        """Return true when state is known."""
        return self._available

    @property
    def state(self):
        """Return the state."""
        return self._state

    async def async_added_to_hass(self):
        """Call to update."""
        async_dispatcher_connect(
            self.hass, SIGNAL_VALLOX_STATE_UPDATE, self._update_callback
        )

    @callback
    def _update_callback(self):
        """Call update method."""
        self.async_schedule_update_ha_state(True)

    async def async_update(self):
        """Fetch state from the ventilation unit."""
        try:
            self._state = self._state_proxy.fetch_metric(self._metric_key)
            self._available = True

        except (OSError, KeyError) as err:
            self._available = False
            _LOGGER.error("Error updating sensor: %s", err)


# There seems to be a quirk with respect to the fan speed reporting. The device
# keeps on reporting the last valid fan speed from when the device was in
# regular operation mode, even if it left that state and has been shut off in
# the meantime.
#
# Therefore, first query the overall state of the device, and report zero
# percent fan speed in case it is not in regular operation mode.
class ValloxFanSpeedSensor(ValloxSensor):
    """Child class for fan speed reporting."""

    async def async_update(self):
        """Fetch state from the ventilation unit."""
        try:
            # If device is in regular operation, continue.
            if self._state_proxy.fetch_metric(METRIC_KEY_MODE) == 0:
                await super().async_update()
            else:
                # Report zero percent otherwise.
                self._state = 0
                self._available = True

        except (OSError, KeyError) as err:
            self._available = False
            _LOGGER.error("Error updating sensor: %s", err)


class ValloxProfileSensor(ValloxSensor):
    """Child class for profile reporting."""

    def __init__(
        self, name, state_proxy, device_class, unit_of_measurement, icon
    ) -> None:
        """Initialize the Vallox sensor."""
        super().__init__(
            name, state_proxy, None, device_class, unit_of_measurement, icon
        )

    async def async_update(self):
        """Fetch state from the ventilation unit."""
        try:
            self._state = self._state_proxy.get_profile()
            self._available = True

        except OSError as err:
            self._available = False
            _LOGGER.error("Error updating sensor: %s", err)


class ValloxFilterRemainingSensor(ValloxSensor):
    """Child class for filter remaining time reporting."""

    async def async_update(self):
        """Fetch state from the ventilation unit."""
        try:
            days_remaining = int(self._state_proxy.fetch_metric(self._metric_key))
            days_remaining_delta = timedelta(days=days_remaining)

            # Since only a delta of days is received from the device, fix the
            # time so the timestamp does not change with every update.
            now = datetime.utcnow().replace(hour=13, minute=0, second=0, microsecond=0)

            self._state = (now + days_remaining_delta).isoformat()
            self._available = True

        except (OSError, KeyError) as err:
            self._available = False
            _LOGGER.error("Error updating sensor: %s", err)
