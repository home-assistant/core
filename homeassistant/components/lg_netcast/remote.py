"""Remote control support for LG Netcast TV."""

from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

from pylgnetcast import LG_COMMAND, LgNetCastClient, LgNetCastError
from requests import RequestException

from homeassistant.components.remote import ATTR_NUM_REPEATS, RemoteEntity
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import LgNetCastConfigEntry
from .const import ATTR_MANUFACTURER, DOMAIN

VALID_COMMANDS: frozenset[str] = frozenset(
    k
    for k in vars(LG_COMMAND)
    if not k.startswith("_") and isinstance(getattr(LG_COMMAND, k), int)
)


async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: LgNetCastConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up LG Netcast Remote from a config entry."""
    client = config_entry.runtime_data
    unique_id = config_entry.unique_id
    if TYPE_CHECKING:
        assert unique_id is not None

    async_add_entities([LgNetCastRemote(client, unique_id)])


class LgNetCastRemote(RemoteEntity):
    """Device that sends commands to an LG Netcast TV."""

    _attr_has_entity_name = True
    _attr_name = None

    def __init__(self, client: LgNetCastClient, unique_id: str) -> None:
        """Initialize the LG Netcast remote."""
        self._client = client
        self._attr_unique_id = unique_id
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, unique_id)},
            manufacturer=ATTR_MANUFACTURER,
        )

    def send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send commands to the TV."""
        num_repeats = kwargs[ATTR_NUM_REPEATS]

        commands: list[int] = []
        for cmd in command:
            if cmd not in VALID_COMMANDS:
                raise ServiceValidationError(f"Unknown command: {cmd!r}")
            commands.append(getattr(LG_COMMAND, cmd))
        for _ in range(num_repeats):
            try:
                with self._client as client:
                    for lg_command in commands:
                        client.send_command(lg_command)
            except LgNetCastError, RequestException:
                self._attr_is_on = False
                self.schedule_update_ha_state()
                return

    def turn_on(self, **kwargs: Any) -> None:
        """Turn on is handled via a separate turn_on trigger."""
        raise NotImplementedError(
            "Turning on the TV is not supported by the LG Netcast remote entity"
        )

    def turn_off(self, **kwargs: Any) -> None:
        """Turn off the TV."""
        self.send_command(["POWER"], **{ATTR_NUM_REPEATS: 1})
