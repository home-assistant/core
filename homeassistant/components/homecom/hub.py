"""Hub for Homecom."""
import aiohttp
from aiohttp import BasicAuth, ClientSession
from homecom.homecom_api import AirConditioner, HomecomApi
from homecom.homecom_auth import HomecomAuth

from homeassistant.core import HomeAssistant

from .config_store import ConfigStore
from .exceptions import CannotConnect, InvalidAuth


class Hub:
    """Hub for Homecom."""

    def __init__(
        self,
        hass: HomeAssistant,
        client_session: ClientSession,
        username: str,
        password: str,
    ) -> None:
        """Initialize."""
        self._store = ConfigStore(hass)
        self._client_session = client_session
        self._homecom_auth = HomecomAuth(
            self._client_session,
            "https://pointt-api.bosch-thermotechnology.com",
            BasicAuth(username, password),
        )
        self._homecom_api = HomecomApi(self._homecom_auth)

    async def authenticate(self) -> bool:
        """Authenticate with Homecom."""
        try:
            await self._homecom_auth.authenticate()
        except aiohttp.ClientConnectionError as exc:
            raise CannotConnect("Error connecting to Homecom") from exc

        auth_is_valid = self._homecom_auth.is_valid()
        if auth_is_valid:
            self._store.set_authorized(
                self._homecom_auth.access_token, self._homecom_auth.refresh_token
            )
        else:
            raise InvalidAuth("Invalid auth")
        return auth_is_valid

    async def get_acs(self) -> list[AirConditioner]:
        """Get all air conditioners."""

        return await self._homecom_api.async_get_acs()

    async def get_ac(self, device_id) -> AirConditioner:
        """Get air conditioner by device id."""
        return await self._homecom_api.async_get_ac(device_id)
