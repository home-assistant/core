from enum import Enum

class OpenAQDeviceSensors(str, Enum):
    """Sensors to report in home assistant."""

    Last_Update = "TIMESTAMP"
    Air_Quality_index = "AQI"
    Particle_Matter_25 = "PM25"
    Particle_Matter_10 = "PM10"
    Particle_Matter_1 = "PM1"
    Concentration_of_Ozone = "OZONE"
    Atmospheric_Pressure = "ATMOSPHERIC_PRESSURE"
    TEMPERATURE = "TEMPERATURE"
    Relative_humidity = "HUMIDITY"
    Concentration_of_Nitrogen_Dioxide = "NITROGEN_DIOXIDE"
    Concentration_of_NITROGEN_MONOXIDE = "NITROGEN_MONOXIDE"
    Concentration_of_Carbon_Monoxide = "CO"
    Concentration_of_Carbon_Dioxide = "CO2"
    Concentration_of_Sulphure_Dioxide = "SULPHUR_DIOXIDE"

async def async_setup_entry(hass, entry, async_add_devices):
    """Configure the sensor platform."""
    pass


class OpenAQSensor(SensorEntity):
    def __init__(
        self,
        hass: HomeAssistant,
        description: SensorDescription,
    ):
        pass

    @property
    def should_poll(self):
        """Return True if entity has to be polled for state.

        False if entity pushes its state to HA.
        """
        return True

    @property
    def state_class(self):
        return SensorStateClass.MEASUREMENT

    @property
    def device_class(self):
        pass

    @property
    def native_value(self):
        pass

    @property
    def native_unit_of_measurement(self):
        pass

    async def async_added_to_hass(self) -> None:
        """Handle entity which will be added."""
        pass
