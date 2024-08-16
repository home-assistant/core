"""Manage Viam client connection."""

from typing import Any

from viam.app.app_client import RobotPart
from viam.app.viam_client import ViamClient
from viam.robot.client import RobotClient
from viam.rpc.dial import Credentials, DialOptions

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_ADDRESS
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from .const import (
    CONF_API_ID,
    CONF_CREDENTIAL_TYPE,
    CONF_ROBOT_ID,
    CONF_SECRET,
    CRED_TYPE_API_KEY,
    CRED_TYPE_LOCATION_SECRET,
    DOMAIN,
)

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
        self.address: str = data.get(CONF_ADDRESS, "")
        self.auth_entity: str = data.get(CONF_API_ID, "")
        self.cred_type: str = data.get(CONF_CREDENTIAL_TYPE, CRED_TYPE_API_KEY)
        self.entry_id = entry_id
        self.hass = hass
        self.robot_id: str = data.get(CONF_ROBOT_ID, "")
        self.secret: str = data.get(CONF_SECRET, "")
        self.viam = viam

    def unload(self) -> None:
        """Clean up any open clients."""
        self.viam.close()

    async def get_robot_client(
        self, robot_secret: str | None, robot_address: str | None
    ) -> RobotClient:
        """Check initialized data to create robot client."""
        address = self.address
        payload = self.secret
        cred_type = self.cred_type
        auth_entity: str | None = self.auth_entity

        if robot_secret is not None:
            if robot_address is None:
                raise ServiceValidationError(
                    "The robot address is required for this connection type.",
                    translation_domain=DOMAIN,
                    translation_key="robot_credentials_required",
                )
            cred_type = CRED_TYPE_LOCATION_SECRET
            auth_entity = None
            address = robot_address
            payload = robot_secret

        if address is None or payload is None:
            raise ServiceValidationError(
                "The necessary credentials for the RobotClient could not be found.",
                translation_domain=DOMAIN,
                translation_key="robot_credentials_not_found",
            )

        credentials = Credentials(type=cred_type, payload=payload)
        robot_options = RobotClient.Options(
            refresh_interval=0,
            dial_options=DialOptions(auth_entity=auth_entity, credentials=credentials),
        )
        return await RobotClient.at_address(address, robot_options)

    async def get_robot_parts(self) -> list[RobotPart]:
        """Retrieve list of robot parts."""
        return await self.viam.app_client.get_robot_parts(robot_id=self.robot_id)
