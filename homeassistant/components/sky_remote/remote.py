"""Home Assistant integration to control a sky box using the remote platform."""

from collections.abc import Iterable
import logging
from typing import Any

from skyboxremote import VALID_KEYS, RemoteControl

from homeassistant.components.remote import RemoteEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import SkyRemoteConfigEntry
from .const import DOMAIN

_LOGGER = logging.getLogger(__name__)


async def async_setup_entry(
    hass: HomeAssistant,
    config: SkyRemoteConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the Sky remote platform."""
    async_add_entities(
        [SkyRemote(config.runtime_data, config.entry_id)],
        True,
    )


class SkyRemote(RemoteEntity):
    """Representation of a Sky Remote."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, remote: RemoteControl, unique_id: str) -> None:
        """Initialize the Sky Remote."""
        self._remote = remote
        self._attr_unique_id = unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            manufacturer="SKY",
            model="Sky Box",
            name=remote.host,
        )

    def turn_on(self, activity: str | None = None, **kwargs: Any) -> None:
        """Send the power on command."""
        self.send_command(["sky"])

    def turn_off(self, activity: str | None = None, **kwargs: Any) -> None:
        """Send the power command."""
        self.send_command(["power"])

    def send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send a list of commands to the device."""
        for cmd in command:
            if cmd not in VALID_KEYS:
                raise ServiceValidationError(
                    f"{cmd} is not in Valid Keys: {VALID_KEYS}"
                )
        try:
            self._remote.send_keys(command)
        except ValueError as err:
            _LOGGER.error("Invalid command: %s. Error: %s", command, err)
            return
        _LOGGER.debug("Successfully sent command %s", command)
