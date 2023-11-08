async def async_setup_entry(hass, entry, async_add_devices):
    """Configure the sensor platform."""
    pass


class ChargePointMetric(SensorEntity):
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
