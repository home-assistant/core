"""Remote for Trinnov integration."""

from __future__ import annotations

from typing import TYPE_CHECKING

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


VALID_COMMANDS = {
    "acoustic_correction_off",
    "acoustic_correction_on",
    "acoustic_correction_toggle",
    "bypass_off",
    "bypass_on",
    "bypass_toggle",
    "dim_off",
    "dim_on",
    "dim_toggle",
    "front_display_off",
    "front_display_on",
    "front_display_toggle",
    "level_alignment_off",
    "level_alignment_on",
    "level_alignment_toggle",
    "mute_off",
    "mute_on",
    "mute_toggle",
    "page_down",
    "page_up",
    "preset_load",
    "quick_optimized_off",
    "quick_optimized_on",
    "quick_optimized_toggle",
    "remapping_mode_set",
    "source_set",
    "time_alignment_off",
    "time_alignment_on",
    "time_alignment_toggle",
    "upmixer_set",
    "volume_down",
    "volume_ramp",
    "volume_set",
    "volume_up",
}


class TrinnovAltitudeRemote(TrinnovAltitudeEntity, RemoteEntity):
    """Representation of a Trinnov Altitude device."""

    _attr_name = None

    @property
    def is_on(self) -> bool:
        """Return true if device is on."""
        return self._device.connected()

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
            try:
                cmd_parts = cmd.split()  # Split the cmd string by spaces
                method_name = cmd_parts[0]  # The first token is the method name
                args_strings = cmd_parts[1:]  # The rest of the tokens are the arguments
                typed_args = [self._cast_to_primitive_type(arg) for arg in args_strings]

                if method_name not in VALID_COMMANDS:
                    raise HomeAssistantError(
                        f"{cmd} is not a known Trinnov Altitude command"
                    )

                await getattr(self._device, method_name)(*typed_args)
            except NotConnectedError as exc:
                raise HomeAssistantError(
                    "Trinnov Altitude must be powered on before sending commands"
                ) from exc
            except TypeError as exc:
                raise HomeAssistantError(
                    f"Command arguments are invalid: {exc}"
                ) from exc

    def _cast_to_primitive_type(self, arg: str) -> bool | int | float | str:
        """Casts command arguments to primitive types that the device expects."""

        # Convert to lowercase for boolean checks
        arg_lower = arg.lower()

        if arg_lower == "true":
            return True

        if arg_lower == "false":
            return False

        # Attempt to convert to int or float
        try:
            return int(arg)
        except ValueError:
            pass

        try:
            return float(arg)
        except ValueError:
            pass

        # Return as string if all else fails
        return arg
