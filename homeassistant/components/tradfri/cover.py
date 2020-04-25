"""Support for IKEA Tradfri covers."""

from homeassistant.components.cover import ATTR_POSITION, CoverEntity

from .base_class import TradfriBaseDevice
from .const import ATTR_MODEL, CONF_GATEWAY_ID, KEY_API, KEY_GATEWAY


async def async_setup_entry(hass, config_entry, async_add_entities):
    """Load Tradfri covers based on a config entry."""
    gateway_id = config_entry.data[CONF_GATEWAY_ID]
    api = hass.data[KEY_API][config_entry.entry_id]
    gateway = hass.data[KEY_GATEWAY][config_entry.entry_id]

    devices_commands = await api(gateway.get_devices())
    devices = await api(devices_commands)
    covers = [dev for dev in devices if dev.has_blind_control]
    if covers:
        async_add_entities(TradfriCover(cover, api, gateway_id) for cover in covers)


class TradfriCover(TradfriBaseDevice, CoverEntity):
    """The platform class required by Home Assistant."""

    def __init__(self, device, api, gateway_id):
        """Initialize a cover."""
        super().__init__(device, api, gateway_id)
        self._unique_id = f"{gateway_id}-{device.id}"

        self._refresh(device)

    @property
    def device_state_attributes(self):
        """Return the state attributes."""
        attr = {ATTR_MODEL: self._device.device_info.model_number}
        return attr

    @property
    def current_cover_position(self):
        """Return current position of cover.

        None is unknown, 0 is closed, 100 is fully open.
        """
        return 100 - self._device_data.current_cover_position

    async def async_set_cover_position(self, **kwargs):
        """Move the cover to a specific position."""
        await self._api(self._device_control.set_state(100 - kwargs[ATTR_POSITION]))

    async def async_open_cover(self, **kwargs):
        """Open the cover."""
        await self._api(self._device_control.set_state(0))

    async def async_close_cover(self, **kwargs):
        """Close cover."""
        await self._api(self._device_control.set_state(100))

    async def async_stop_cover(self, **kwargs):
        """Close cover."""
        await self._api(self._device_control.trigger_blind())

    @property
    def is_closed(self):
        """Return if the cover is closed or not."""
        return self.current_cover_position == 0

    def _refresh(self, device):
        """Refresh the cover data."""
        super()._refresh(device)
        self._device = device

        # Caching of BlindControl and cover object
        self._device_control = device.blind_control
        self._device_data = device.blind_control.blinds[0]
