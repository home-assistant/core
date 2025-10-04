"""The Matrix bot component."""

from __future__ import annotations

import os

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

from .bot import MatrixBot
from .services import async_setup_services
from .types import CONFIG_SCHEMA, DOMAIN

SESSION_FILE = ".matrix.conf"


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Matrix bot component."""
    # Validate configuration
    config = CONFIG_SCHEMA(config)[DOMAIN]

    hass.data[DOMAIN] = MatrixBot(
        hass=hass,
        config_file=os.path.join(hass.config.path(), SESSION_FILE),
        homeserver=config["homeserver"],
        verify_ssl=config["verify_ssl"],
        username=config["username"],
        password=config["password"],
        device_id=config.get("device_id", "Home Assistant"),
        listening_rooms=config["rooms"],
        commands=config["commands"],
    )

    async_setup_services(hass)

    return True
