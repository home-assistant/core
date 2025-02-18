"""Device Sensor for PG LAB Electronics."""

from pypglab.device import Device as PyPGLabDevice

from homeassistant.core import callback

from .entity import PGLabEntity


class PGLabDeviceSensor:
    """Keep PGLab device sensor update."""

    def __init__(self, pglab_device: PyPGLabDevice) -> None:
        """Initialize the device sensor."""

        # get a reference of PG Lab device internal sensors state
        self._sensors = pglab_device.sensors

        self._ha_sensors: list[PGLabEntity] = []  # list of HA entity sensors

    async def subscribe_topics(self):
        """Subscribe to the device sensors topics."""
        self._sensors.set_on_state_callback(self.state_updated)
        await self._sensors.subscribe_topics()

    def add_ha_sensor(self, entity: PGLabEntity) -> None:
        """Add a new HA sensor to the list."""
        self._ha_sensors.append(entity)

    def remove_ha_sensor(self, entity: PGLabEntity) -> None:
        """Remove a HA sensor from the list."""
        self._ha_sensors.remove(entity)

    @callback
    def state_updated(self, payload: str) -> None:
        """Handle state updates."""

        # notify all HA sensors that PG LAB device sensors fields have been updated
        for s in self._ha_sensors:
            s.state_updated(payload)

    @property
    def state(self):
        """Return the device sensor state."""
        return self._sensors.state

    @property
    def sensors(self):
        """Return the pypglab device sensor."""
        return self._sensors


async def create_pglab_device_sensor(pglab_device: PyPGLabDevice):
    """Create a new PGLab device sensor."""
    device_sensor = PGLabDeviceSensor(pglab_device)
    await device_sensor.subscribe_topics()
    return device_sensor
