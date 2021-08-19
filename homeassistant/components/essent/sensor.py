"""Support for Essent API."""
from __future__ import annotations

from datetime import timedelta

from pyessent import PyEssent
import voluptuous as vol

from homeassistant.components.sensor import PLATFORM_SCHEMA, SensorEntity
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME, ENERGY_KILO_WATT_HOUR
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle

SCAN_INTERVAL = timedelta(hours=1)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {vol.Required(CONF_USERNAME): cv.string, vol.Required(CONF_PASSWORD): cv.string}
)


def setup_platform(hass, config, add_devices, discovery_info=None):
    """Set up the Essent platform."""
    username = config[CONF_USERNAME]
    password = config[CONF_PASSWORD]

    essent = EssentBase(username, password)
    meters = []
    for meter in essent.retrieve_meters():
        data = essent.retrieve_meter_data(meter)
        for tariff in data["values"]["LVR"]:
            meters.append(
                EssentMeter(
                    essent,
                    meter,
                    data["type"],
                    tariff,
                    data["values"]["LVR"][tariff]["unit"],
                )
            )

    if not meters:
        hass.components.persistent_notification.create(
            "Couldn't find any meter readings. "
            "Please ensure Verbruiks Manager is enabled in Mijn Essent "
            "and at least one reading has been logged to Meterstanden.",
            title="Essent",
            notification_id="essent_notification",
        )
        return

    add_devices(meters, True)


class EssentBase:
    """Essent Base."""

    def __init__(self, username, password):
        """Initialize the Essent API."""
        self._username = username
        self._password = password
        self._meter_data = {}

        self.update()

    def retrieve_meters(self):
        """Retrieve the list of meters."""
        return self._meter_data.keys()

    def retrieve_meter_data(self, meter):
        """Retrieve the data for this meter."""
        return self._meter_data[meter]

    @Throttle(timedelta(minutes=30))
    def update(self):
        """Retrieve the latest meter data from Essent."""
        essent = PyEssent(self._username, self._password)
        eans = set(essent.get_EANs())
        for possible_meter in eans:
            meter_data = essent.read_meter(possible_meter, only_last_meter_reading=True)
            if meter_data:
                self._meter_data[possible_meter] = meter_data


class EssentMeter(SensorEntity):
    """Representation of Essent measurements."""

    def __init__(self, essent_base, meter, meter_type, tariff, unit):
        """Initialize the sensor."""
        self._state = None
        self._essent_base = essent_base
        self._meter = meter
        self._type = meter_type
        self._tariff = tariff
        self._unit = unit

    @property
    def unique_id(self) -> str | None:
        """Return a unique ID."""
        return f"{self._meter}-{self._type}-{self._tariff}"

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"Essent {self._type} ({self._tariff})"

    @property
    def native_value(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def native_unit_of_measurement(self):
        """Return the unit of measurement."""
        if self._unit.lower() == "kwh":
            return ENERGY_KILO_WATT_HOUR

        return self._unit

    def update(self):
        """Fetch the energy usage."""
        # Ensure our data isn't too old
        self._essent_base.update()

        # Retrieve our meter
        data = self._essent_base.retrieve_meter_data(self._meter)

        # Set our value
        self._state = next(
            iter(data["values"]["LVR"][self._tariff]["records"].values())
        )
