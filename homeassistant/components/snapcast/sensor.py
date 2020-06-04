"""Platform for sensor integration."""
from homeassistant.helpers.entity import Entity

from .const import (
    STREAM_PREFIX,
    DATA_KEY,
    SERVER,
    HPID,
    STREAM,
)


from homeassistant.const import (
    STATE_IDLE,
    STATE_PLAYING,
    STATE_UNKNOWN,
)


async def async_setup_platform(hass, config, async_add_entities, discovery_info=None):
    """Set up the sensor platform."""
    server = hass.data[DATA_KEY][SERVER]
    hpid = hass.data[DATA_KEY][HPID]

    streams = [SnapcastStreamSensor(stream, hpid) for stream in server.streams]

    hass.data[DATA_KEY][STREAM] = streams
    async_add_entities(streams)


class SnapcastStreamSensor(Entity):
    """Representation of a sensor."""

    def __init__(self, stream, uid_part):
        """Initialize the sensor."""
        stream.set_callback(self.schedule_update_ha_state)
        self._stream = stream
        self._uid = f"{STREAM_PREFIX}{uid_part}_{self._stream.identifier}"

    @property
    def name(self):
        """Return the name of the sensor."""
        return f"{STREAM_PREFIX}{self._stream.friendly_name}"

    @property
    def state(self):
        """Return the state of the sensor."""
        return {
            "idle": STATE_IDLE,
            "playing": STATE_PLAYING,
            "unknown": STATE_UNKNOWN,
        }.get(self._stream.status, STATE_UNKNOWN)
