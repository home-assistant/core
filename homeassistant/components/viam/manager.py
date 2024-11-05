"""Manage Viam client connection."""

from typing import Any

from viam.app.app_client import RobotPart
from viam.app.viam_client import ViamClient
from viam.robot.client import RobotClient

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from .const import CONF_API_ID, CONF_MACHINE_ID, DOMAIN

type ViamConfigEntry = ConfigEntry[ViamManager]


class ViamManager:
    """Manage Viam client and entry data."""

    def __init__(
        self,
        hass: HomeAssistant,
        viam: ViamClient,
        entry_id: str,
        data: dict[str, Any],
    ) -> None:
        """Store initialized client and user input data."""
        self.api_key: str = data.get(CONF_API_KEY, "")
        self.api_key_id: str = data.get(CONF_API_ID, "")
        self.entry_id = entry_id
        self.hass = hass
        self.machine_id: str = data.get(CONF_MACHINE_ID, "")
        self.viam = viam

    def unload(self) -> None:
        """Clean up any open clients."""
        self.viam.close()

    async def get_robot_client(self) -> RobotClient:
        """Check initialized data to create robot client."""
        api_key = self.api_key
        api_key_id = self.api_key_id

        machine = next(iter(await self.get_machine_parts()))
        machine_address = machine.fqdn

        if machine_address is None:
            raise ServiceValidationError(
                "The machine address could not be found. It may be offline.",
                translation_domain=DOMAIN,
                translation_key="machine_credentials_required",
            )

        if api_key is None:
            raise ServiceValidationError(
                "The necessary credentials for connecting to the machine could not be found.",
                translation_domain=DOMAIN,
                translation_key="machine_credentials_not_found",
            )

        robot_options = RobotClient.Options.with_api_key(api_key, api_key_id)
        return await RobotClient.at_address(machine_address, robot_options)

    async def get_machine_parts(self) -> list[RobotPart]:
        """Retrieve list of robot parts."""
        return await self.viam.app_client.get_robot_parts(robot_id=self.machine_id)
