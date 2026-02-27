"""Remote for Trinnov integration."""

from __future__ import annotations
from typing import TYPE_CHECKING

from trinnov_altitude.command_bridge import (
    VALID_COMMANDS,
    normalize_args,
    parse_command,
)
from trinnov_altitude.exceptions import NoMacAddressError, NotConnectedError

from homeassistant.components.remote import RemoteEntity
from homeassistant.exceptions import HomeAssistantError

from .const import DOMAIN
from .entity import TrinnovAltitudeEntity

if TYPE_CHECKING:
    from collections.abc import Iterable
    from typing import Any

    from homeassistant.config_entries import ConfigEntry
    from homeassistant.core import HomeAssistant
    from homeassistant.helpers.entity_platform import AddEntitiesCallback


async def async_setup_entry(
    hass: HomeAssistant, entry: ConfigEntry, async_add_entities: AddEntitiesCallback
) -> None:
    """Set up the platform from a config entry."""
    entities = [TrinnovAltitudeRemote(hass.data[DOMAIN][entry.entry_id])]
    async_add_entities(entities)


class TrinnovAltitudeRemote(TrinnovAltitudeEntity, RemoteEntity):
    """Representation of a Trinnov Altitude device."""

    _attr_name = None

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._device.connected and self._device.state.synced

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn the device on."""
        try:
            self._device.power_on()
        except NoMacAddressError as exc:
            raise HomeAssistantError(
                "Trinnov Altitude is not configured with a mac address, which is required to power it on."
            ) from exc

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn the device off."""
        await self._device.power_off()

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send a command to a device."""
        for cmd in command:
            method_name: str | None = None
            try:
                parsed = parse_command(cmd)
                method_name = parsed.method_name

                if method_name not in VALID_COMMANDS:
                    raise HomeAssistantError(
                        f"'{method_name}' is not a valid Trinnov Altitude command"
                    )

                typed_args = normalize_args(method_name, parsed.args)
                await getattr(self._device, method_name)(*typed_args)
            except NotConnectedError as exc:
                raise HomeAssistantError(
                    "Trinnov Altitude must be powered on before sending commands"
                ) from exc
            except TypeError as exc:
                raise HomeAssistantError(
                    f"Invalid arguments for command '{method_name or cmd}'. Expected format: <command> <arg1> <arg2> ..."
                ) from exc
            except ValueError as exc:
                raise HomeAssistantError(str(exc)) from exc
