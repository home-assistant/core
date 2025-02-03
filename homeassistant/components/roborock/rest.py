"""Roborock Rest API."""

import logging

from roborock.containers import HomeDataDevice, HomeDataScene, UserData
from roborock.exceptions import RoborockException
from roborock.web_api import RoborockApiClient

from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


class RoborockRestApi:
    """Class to manage fetching data from the rest API."""

    def __init__(
        self,
        device: HomeDataDevice,
        api_client: RoborockApiClient,
        user_data: UserData,
    ) -> None:
        """Initialize."""
        self._device = device
        self._user_data = user_data
        self._api_client = api_client

    async def get_scenes(self) -> list[HomeDataScene]:
        """Get scenes."""
        try:
            return await self._api_client.get_scenes(self._user_data, self._device.duid)
        except RoborockException as err:
            _LOGGER.warning(
                "Failed getting scenes of %s",
                self._device.name,
            )
            _LOGGER.debug(err)
            return []

    async def execute_scene(self, scene_id: int) -> None:
        """Execute scene."""
        try:
            await self._api_client.execute_scene(self._user_data, scene_id)
        except RoborockException as err:
            _LOGGER.error("Failed to execute scene %s %s", scene_id, err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="command_failed",
                translation_placeholders={
                    "command": "execute_scene",
                },
            ) from err
