"""Generic remote entities backed by Home Assistant infrared transmitters."""

import asyncio
from collections.abc import Iterable, Mapping
import logging
from typing import Any, cast

from homeassistant.components import infrared
from homeassistant.components.remote import RemoteEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant, split_entity_id
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .command import RawInfraredCommand, parse_remote_command
from .const import (
    CONF_INFRARED_ENTITY_ID,
    CONF_REMOTE_COMMANDS,
    CONF_REMOTE_ID,
    CONF_REMOTE_NAME,
    CONF_VIRTUAL_REMOTES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)


def _raise_invalid_remote_commands() -> None:
    """Raise when remote commands are not configured as a mapping."""
    raise TypeError("commands must be a mapping")


PARALLEL_UPDATES = 1
POWER_ON_COMMAND = "power_on"
POWER_OFF_COMMAND = "power_off"
POWER_TOGGLE_COMMANDS = ("toggle", "power_toggle")
REMOTE_DEVICE_INFO = "remote_device_info"
REMOTE_UNIQUE_ID_PREFIX = "remote_unique_id_prefix"

# Kept because tests and callers use these parser symbols directly. They are
# command-format compatibility aliases, not iTach hardware compatibility.
_RawInfraredCommand = RawInfraredCommand
_parse_remote_command = parse_remote_command


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up user-configured infrared-backed remote entities."""
    platform_data = _remote_platform_data(hass, entry)
    runtime_data = getattr(entry, "runtime_data", None)

    unique_id_prefix = str(
        platform_data.get(REMOTE_UNIQUE_ID_PREFIX)
        or getattr(entry, "unique_id", None)
        or getattr(entry, "entry_id", None)
        or getattr(runtime_data, "device_id", None)
        or "remote"
    )
    device_info = cast(DeviceInfo | None, platform_data.get(REMOTE_DEVICE_INFO))

    virtual_remotes = _virtual_remotes(entry)

    entities: list[InfraredRemoteEntity] = []
    for remote_config in virtual_remotes:
        try:
            remote_id = str(remote_config[CONF_REMOTE_ID])
            name = str(remote_config[CONF_REMOTE_NAME])
            infrared_entity_id = _required_infrared_entity_id(remote_config)
            commands_raw = remote_config.get(CONF_REMOTE_COMMANDS, {})
            if not isinstance(commands_raw, Mapping):
                _raise_invalid_remote_commands()
            commands = {
                str(command_name): str(command_payload)
                for command_name, command_payload in commands_raw.items()
            }
        except KeyError, TypeError, ValueError:
            _LOGGER.warning(
                "Skipping malformed remote configuration: %s",
                remote_config,
            )
            continue

        entities.append(
            InfraredRemoteEntity(
                remote_id=remote_id,
                name=name,
                infrared_entity_id=infrared_entity_id,
                commands=commands,
                unique_id_prefix=unique_id_prefix,
                device_info=device_info,
                translation_domain=DOMAIN,
            )
        )

    async_add_entities(entities, update_before_add=False)


class InfraredRemoteEntity(RemoteEntity):
    """User-configured remote backed by an infrared transmitter entity."""

    _attr_has_entity_name = False
    _attr_is_on = True
    _attr_available = True
    _attr_assumed_state = True

    def __init__(
        self,
        *,
        remote_id: str,
        name: str,
        infrared_entity_id: str,
        commands: dict[str, str] | None,
        unique_id_prefix: str,
        device_info: DeviceInfo | None,
        translation_domain: str = DOMAIN,
    ) -> None:
        """Initialize the remote entity."""
        self._remote_id = remote_id
        self._infrared_entity_id = _normalize_infrared_entity_id(infrared_entity_id)
        self._commands = commands or {}
        self._translation_domain = translation_domain

        self._attr_name = name
        self._attr_unique_id = f"{unique_id_prefix}_remote_{remote_id}"
        self._attr_device_info = device_info

    @property
    def available(self) -> bool:
        """Return whether the configured infrared entity is currently usable."""
        hass = _entity_hass(self)
        if hass is None:
            return bool(self._attr_available)

        state = hass.states.get(self._infrared_entity_id)
        if state is None or state.state == STATE_UNAVAILABLE:
            return False

        return bool(self._attr_available)

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Send power_on when configured and mark the remote on."""
        if POWER_ON_COMMAND not in self._commands:
            return

        await self._async_send_named_command(POWER_ON_COMMAND, kwargs)
        self._attr_is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Send power_off when configured and mark the remote off."""
        if POWER_OFF_COMMAND not in self._commands:
            return

        await self._async_send_named_command(POWER_OFF_COMMAND, kwargs)
        self._attr_is_on = False
        self.async_write_ha_state()

    async def async_toggle(self, **kwargs: Any) -> None:
        """Send toggle command when configured and toggle remote state."""
        command_name = next(
            (name for name in POWER_TOGGLE_COMMANDS if name in self._commands),
            None,
        )
        if command_name is None:
            return

        await self._async_send_named_command(command_name, kwargs)
        self._attr_is_on = not bool(self._attr_is_on)
        self.async_write_ha_state()

    async def async_send_command(
        self,
        command: Iterable[str],
        **kwargs: Any,
    ) -> None:
        """Send one or more named or raw IR commands."""
        delay_secs = _coerce_non_negative_float(
            kwargs.get("delay_secs", 0),
            "delay_secs",
            self._translation_domain,
        )
        num_repeats = _coerce_positive_int(
            kwargs.get("num_repeats", 1),
            "num_repeats",
            self._translation_domain,
        )
        commands = [command] if isinstance(command, str) else list(command)
        total_sends = num_repeats * len(commands)
        sends_done = 0

        for _ in range(num_repeats):
            for command_name_or_raw in commands:
                await self._async_send_one(str(command_name_or_raw), kwargs)
                sends_done += 1
                if delay_secs > 0 and sends_done < total_sends:
                    await asyncio.sleep(delay_secs)

    async def _async_send_named_command(
        self,
        command_name: str,
        kwargs: dict[str, Any],
    ) -> None:
        """Send a configured named command."""
        if command_name not in self._commands:
            raise _remote_error(
                self._translation_domain,
                "remote_command_missing",
                {"command": command_name},
            )
        await self._async_send_one(command_name, kwargs)

    async def _async_send_one(
        self,
        command_name_or_raw: str,
        kwargs: dict[str, Any],
    ) -> None:
        """Resolve and send one named or raw command."""
        hass = _entity_hass(self)
        if hass is None:
            raise _remote_error(
                self._translation_domain,
                "remote_infrared_missing",
                {"entity_id": self._infrared_entity_id},
            )

        command_payload = self._commands.get(command_name_or_raw, command_name_or_raw)
        ir_command = parse_remote_command(command_payload, kwargs)
        await self._async_send_infrared_command(hass, ir_command)

    async def _async_send_infrared_command(
        self,
        hass: HomeAssistant,
        ir_command: RawInfraredCommand,
    ) -> None:
        """Send a parsed infrared command through the configured transmitter."""
        try:
            await infrared.async_send_command(
                hass,
                self._infrared_entity_id,
                ir_command,
                context=getattr(self, "_context", None),
            )
        except HomeAssistantError:
            raise
        except Exception as err:
            _LOGGER.warning(
                "Failed sending remote command via infrared entity %s",
                self._infrared_entity_id,
            )
            raise _remote_error(
                self._translation_domain,
                "remote_send_failed",
                {"error": str(err)},
            ) from err

    def _resolve_infrared_entity_id(self) -> str:
        """Return the configured infrared entity id."""
        return self._infrared_entity_id

    def _infrared_entity_id_for_log(self) -> str:
        """Return the configured infrared entity id for logs and errors."""
        return self._infrared_entity_id


def _virtual_remotes(entry: ConfigEntry) -> list[Mapping[str, Any]]:
    """Return virtual remote configs from options or data.

    Options take precedence for integrations that manage remotes after setup.
    Data fallback lets other integrations share this remote platform while
    storing the same remote config shape directly in the config entry data.
    """
    options = getattr(entry, "options", {})
    data = getattr(entry, "data", {})

    if CONF_VIRTUAL_REMOTES in options:
        remotes = options[CONF_VIRTUAL_REMOTES]
    elif CONF_VIRTUAL_REMOTES in data:
        remotes = data[CONF_VIRTUAL_REMOTES]
    else:
        return []

    if not isinstance(remotes, list):
        return []

    return [remote for remote in remotes if isinstance(remote, Mapping)]


def _remote_platform_data(hass: HomeAssistant, entry: ConfigEntry) -> dict[str, Any]:
    """Return optional platform data supplied by the owning integration."""
    domain_data = hass.data.get(DOMAIN, {})
    entry_id = getattr(entry, "entry_id", None)
    if entry_id is None:
        return {}
    entry_data = domain_data.get(entry_id, {})
    return entry_data if isinstance(entry_data, dict) else {}


def _required_infrared_entity_id(remote_config: Mapping[str, Any]) -> str:
    """Return the required infrared entity id from a remote config."""
    return _normalize_infrared_entity_id(remote_config[CONF_INFRARED_ENTITY_ID])


def _normalize_infrared_entity_id(value: str) -> str:
    """Normalize and validate an infrared entity id string."""
    entity_id = value.strip()
    if not entity_id:
        raise ValueError("infrared entity id is required")
    try:
        domain, _object_id = split_entity_id(entity_id)
    except ValueError as err:
        raise ValueError("infrared entity id must be a valid entity id") from err
    if domain != infrared.DOMAIN:
        raise ValueError("infrared entity id must belong to the infrared domain")
    return entity_id


def _coerce_non_negative_float(
    value: Any,
    field: str,
    translation_domain: str,
) -> float:
    """Coerce a non-negative float service parameter."""
    try:
        result = float(value)
    except (TypeError, ValueError) as err:
        raise _remote_error(
            translation_domain,
            "remote_invalid_service_parameter",
            {"error": f"{field} must be a number"},
        ) from err

    if result < 0:
        raise _remote_error(
            translation_domain,
            "remote_invalid_service_parameter",
            {"error": f"{field} must be greater than or equal to 0"},
        )

    return result


def _coerce_positive_int(
    value: Any,
    field: str,
    translation_domain: str,
) -> int:
    """Coerce a positive integer service parameter."""
    try:
        result = int(value)
    except (TypeError, ValueError) as err:
        raise _remote_error(
            translation_domain,
            "remote_invalid_service_parameter",
            {"error": f"{field} must be an integer"},
        ) from err

    if result < 1:
        raise _remote_error(
            translation_domain,
            "remote_invalid_service_parameter",
            {"error": f"{field} must be at least 1"},
        )

    return result


def _remote_error(
    translation_domain: str,
    translation_key: str,
    placeholders: dict[str, str],
) -> HomeAssistantError:
    """Build a translated Home Assistant error."""
    return HomeAssistantError(
        translation_domain=translation_domain,
        translation_key=translation_key,
        translation_placeholders=placeholders,
    )


def _entity_hass(entity: RemoteEntity) -> HomeAssistant | None:
    """Return an entity's hass instance without upsetting static typing."""
    return cast(HomeAssistant | None, getattr(entity, "hass", None))
