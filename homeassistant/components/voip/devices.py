"""Class to store devices."""

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import storage, device_registry as dr, entity_registry as er

from .const import DOMAIN

STORAGE_VERSION = 1

STORAGE_KEY = DOMAIN


class VoIPDevices:
    """Class to store devices."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize VoIP devices."""
        self.hass = hass
        self._store = storage.Store(hass, STORAGE_VERSION, STORAGE_KEY)
        self._devices = {}

    async def async_load(self) -> None:
        """Load devices."""
        data = await self._store.async_load()

        if data is None:
            return

        self._devices = data

    @callback
    def async_allow_call(self, ip_address: str) -> bool:
        """Check if a call is allowed."""
        dev_reg = dr.async_get(self.hass)

        device = dev_reg.async_get_device({(DOMAIN, ip_address)})

        if device is None:
            # Create device
            ...
            return False

        ent_reg = er.async_get(self.hass)

        allowed_call_entity_id = ent_reg.async_get_entity_id(
            "switch", DOMAIN, ip_address
        )

        return self.hass.states.get(allowed_call_entity_id).state == "on"
