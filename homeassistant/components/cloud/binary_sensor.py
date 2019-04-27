"""Support for Home Assistant Cloud binary sensors."""
import asyncio

from homeassistant.components.binary_sensor import BinarySensorDevice
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from .const import DISPATCHER_REMOTE_UPDATE, DOMAIN


WAIT_UNTIL_CHANGE = 3


async def async_setup_platform(
        hass, config, async_add_entities, discovery_info=None):
    """Set up the cloud binary sensors."""
    if discovery_info is None:
        return
    cloud = hass.data[DOMAIN]

    async_add_entities([CloudRemoteBinary(cloud)])


class CloudRemoteBinary(BinarySensorDevice):
    """Representation of an Cloud Remote UI Connection binary sensor."""

    def __init__(self, cloud):
        """Initialize the binary sensor."""
        self.cloud = cloud
        self._unsub_dispatcher = None

    @property
    def name(self) -> str:
        """Return the name of the binary sensor, if any."""
        return "Remote UI"

    @property
    def unique_id(self) -> str:
        """Return a unique ID."""
        return "cloud-remote-ui-connectivity"

    @property
    def is_on(self) -> bool:
        """Return true if the binary sensor is on."""
        return self.cloud.remote.is_connected

    @property
    def device_class(self) -> str:
        """Return the class of this device, from component DEVICE_CLASSES."""
        return 'connectivity'

    @property
    def available(self) -> bool:
        """Return True if entity is available."""
        return self.cloud.remote.certificate is not None

    @property
    def should_poll(self) -> bool:
        """Return True if entity has to be polled for state."""
        return False

    async def async_added_to_hass(self):
        """Register update dispatcher."""
        async def async_state_update(data):
            """Update callback."""
            await asyncio.sleep(WAIT_UNTIL_CHANGE)
            self.async_schedule_update_ha_state()

        self._unsub_dispatcher = async_dispatcher_connect(
            self.hass, DISPATCHER_REMOTE_UPDATE, async_state_update)

    async def async_will_remove_from_hass(self):
        """Register update dispatcher."""
        if self._unsub_dispatcher is not None:
            self._unsub_dispatcher()
            self._unsub_dispatcher = None
