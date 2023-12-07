"""API for iotty bound to Home Assistant OAuth."""

import asyncio
import logging
from typing import Any

from aiohttp import ClientSession
from iottycloud.cloudapi import CloudApi
from iottycloud.device import Device
from iottycloud.verbs import RESULT, STATUS

from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.helpers.entity import Entity

from .const import IOTTYAPI_BASE, OAUTH2_CLIENT_ID

_LOGGER = logging.getLogger(__name__)

PLATFORMS: list[Platform] = [Platform.SWITCH]


class IottyProxy(CloudApi):
    """Provide iotty authentication tied to an OAuth2 based config entry."""

    _devices: list[Device]
    _entities: dict
    _coroutine: Any

    def __init__(
        self,
        hass: HomeAssistant,
        websession: ClientSession,
        oauth_session: config_entry_oauth2_flow.OAuth2Session,
    ) -> None:
        """Initialize iotty auth."""

        super().__init__(websession, IOTTYAPI_BASE, OAUTH2_CLIENT_ID)
        if oauth_session is None:
            raise ValueError("oauth_session")
        self._oauth_session = oauth_session
        self._devices = []
        self._entities = {}
        self._hass = hass

    async def init(self, entry):
        """Initialize iotty middleware."""
        _LOGGER.debug("Initializing iotty middleware")
        ## Improve efficiency by removing
        # with suppress(Exception):
        self._devices = await self.get_devices()

        _LOGGER.debug("There are %d Devices", len(self._devices))

        if len(self._devices) > 0:
            self._coroutine = self._hass.async_create_background_task(
                self._polling(), "polling_task"
            )

        await self._hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    async def devices(self, device_type: str) -> Any:
        """Get devices for a specific type."""

        _LOGGER.debug("There are %d devices", len(self._devices))

        ret = [d for d in self._devices if d.device_type == device_type]

        return ret

    def store_entity(self, device_id: str, entity: Entity) -> None:
        """Store iotty device within Hass entities."""
        _LOGGER.debug("Storing device '%s' in entities", device_id)
        self._entities[device_id] = entity

    async def _polling(self) -> None:
        """Continuous polling from iottyCloud."""
        while True:
            _LOGGER.debug("_polling routine from iottyCloud")

            for device in self._devices:
                res = await self.get_status(device.device_id)

                if RESULT not in res or STATUS not in res[RESULT]:
                    _LOGGER.warning(
                        "Unable to read status for device %s", device.device_id
                    )
                else:
                    status = res[RESULT][STATUS]
                    _LOGGER.debug(
                        "Retrieved status: '%s' for device %s", status, device.device_id
                    )
                    device.update_status(status)

                    if device.device_id not in self._entities:
                        _LOGGER.warning(
                            "Cannot find device %s (of type: %s) in _entities",
                            device.device_id,
                            device.device_type,
                        )
                    else:
                        self._entities[device.device_id].schedule_update_ha_state()

            await asyncio.sleep(5)

    async def async_get_access_token(self) -> str:
        """Return a valid access token."""

        if not self._oauth_session.valid_token:
            await self._oauth_session.async_ensure_token_valid()

        return self._oauth_session.token["access_token"]
