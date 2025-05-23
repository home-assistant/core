"""Support for the EZcontrol XS1 gateway."""

import asyncio

from xs1_api_client.device import XS1Device

from homeassistant.helpers.entity import Entity

# Lock used to limit the amount of concurrent update requests
# as the XS1 Gateway can only handle a very
# small amount of concurrent requests
UPDATE_LOCK = asyncio.Lock()


class XS1DeviceEntity(Entity):
    """Representation of a base XS1 device."""

    def __init__(self, device: XS1Device) -> None:
        """Initialize the XS1 device."""
        self.device = device

    async def async_update(self) -> None:
        """Retrieve latest device state."""
        async with UPDATE_LOCK:
            await self.hass.async_add_executor_job(self.device.update)
