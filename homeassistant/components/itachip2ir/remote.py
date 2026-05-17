"""Remote entities for Global Caché iTach IP2IR virtual remotes."""

import asyncio
from collections.abc import Iterable, Mapping
import logging
from typing import Any

from homeassistant.components import infrared
from homeassistant.components.remote import RemoteEntity
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import ItachConfigEntry
from .command import parse_remote_command as _parse_remote_command
from .const import (
    CONF_INFRARED_ENTITY_ID,
    CONF_REMOTE_COMMANDS,
    CONF_REMOTE_ID,
    CONF_REMOTE_NAME,
    CONF_VIRTUAL_REMOTES,
    DOMAIN,
)

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


def _as_str_mapping(value: Any) -> dict[str, str] | None:
    """Return a string mapping or None when the value is malformed."""
    if not isinstance(value, Mapping):
        return None

    result: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, str):
            return None
        result[key] = item

    return result


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ItachConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up configured virtual remote entities."""
    runtime_data = entry.runtime_data
    entry_data = getattr(entry, "data", {})
    configured_remotes = entry.options.get(
        CONF_VIRTUAL_REMOTES,
        entry_data.get(CONF_VIRTUAL_REMOTES, []),
    )

    entities: list[InfraredRemoteEntity] = []

    if not isinstance(configured_remotes, list):
        _LOGGER.warning("Ignoring malformed iTach virtual remote configuration")
        async_add_entities(entities)
        return

    for remote_config in configured_remotes:
        if not isinstance(remote_config, Mapping):
            continue

        remote_id = remote_config.get(CONF_REMOTE_ID)
        name = remote_config.get(CONF_REMOTE_NAME)
        infrared_entity_id = remote_config.get(CONF_INFRARED_ENTITY_ID)
        commands = _as_str_mapping(remote_config.get(CONF_REMOTE_COMMANDS, {}))

        if (
            not isinstance(remote_id, str)
            or not isinstance(name, str)
            or not isinstance(infrared_entity_id, str)
            or commands is None
        ):
            _LOGGER.debug("Skipping malformed iTach virtual remote entry")
            continue

        entities.append(
            InfraredRemoteEntity(
                remote_id=remote_id,
                name=name,
                infrared_entity_id=infrared_entity_id,
                commands=commands,
                unique_id_prefix=runtime_data.device_id,
                device_info=DeviceInfo(
                    identifiers={(DOMAIN, runtime_data.device_id)},
                    name=f"iTach IP2IR ({runtime_data.host})",
                    manufacturer="Global Caché",
                    model="iTach IP2IR",
                    configuration_url=f"http://{runtime_data.host}",
                ),
            )
        )

    async_add_entities(entities)


class InfraredRemoteEntity(RemoteEntity):
    """Virtual remote backed by a Home Assistant infrared entity."""

    _attr_should_poll = False

    def __init__(
        self,
        *,
        remote_id: str,
        name: str,
        infrared_entity_id: str,
        commands: dict[str, str] | None,
        unique_id_prefix: str,
        device_info: DeviceInfo,
    ) -> None:
        """Initialize the virtual remote."""
        self._attr_name = name
        self._attr_unique_id = f"{unique_id_prefix}_remote_{remote_id}"
        self._attr_device_info = device_info
        self._infrared_entity_id = infrared_entity_id
        self._commands = commands or {}
        self._is_on = True

    @property
    def is_on(self) -> bool:
        """Return whether the virtual remote is on."""
        return self._is_on

    @property
    def available(self) -> bool:
        """Return whether the backing infrared entity is available."""
        hass = getattr(self, "hass", None)
        if hass is None:
            return True

        state = hass.states.get(self._infrared_entity_id)
        if state is None:
            return False

        return state.state != STATE_UNAVAILABLE

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the virtual remote."""
        if "power_on" not in self._commands:
            return

        await self._async_send_named_command("power_on", kwargs)
        self._is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the virtual remote."""
        if "power_off" not in self._commands:
            return

        await self._async_send_named_command("power_off", kwargs)
        self._is_on = False
        self.async_write_ha_state()

    async def async_toggle(self, **kwargs: Any) -> None:
        """Toggle the virtual remote."""
        command = None
        if "toggle" in self._commands:
            command = "toggle"
        elif "power_toggle" in self._commands:
            command = "power_toggle"

        if command is None:
            return

        await self._async_send_named_command(command, kwargs)
        self._is_on = not self._is_on
        self.async_write_ha_state()

    async def async_send_command(
        self,
        command: Iterable[str],
        **kwargs: Any,
    ) -> None:
        """Send one or more commands through the backing infrared entity."""
        num_repeats = kwargs.pop("num_repeats", 1)
        delay_secs = kwargs.pop("delay_secs", 0)

        if not isinstance(num_repeats, int) or num_repeats < 1:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="remote_invalid_service_parameter",
                translation_placeholders={
                    "error": "num_repeats must be a positive integer"
                },
            )

        if not isinstance(delay_secs, (int, float)) or delay_secs < 0:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="remote_invalid_service_parameter",
                translation_placeholders={
                    "error": "delay_secs must be a non-negative number"
                },
            )

        commands = [command] if isinstance(command, str) else list(command)
        total = len(commands) * num_repeats
        sent = 0

        for _ in range(num_repeats):
            for item in commands:
                if not isinstance(item, str):
                    raise HomeAssistantError(
                        translation_domain=DOMAIN,
                        translation_key="remote_invalid_service_parameter",
                        translation_placeholders={"error": "command must be a string"},
                    )

                await self._async_send_named_command(item, kwargs)
                sent += 1

                if delay_secs and sent < total:
                    await asyncio.sleep(delay_secs)

    async def _async_send_named_command(
        self,
        command: str,
        kwargs: dict[str, Any] | None = None,
    ) -> None:
        """Resolve and send a named or raw infrared command."""
        raw_command = self._commands.get(command, command)
        ir_command = _parse_remote_command(raw_command, kwargs or {})
        entity_id = self._resolve_infrared_entity_id()

        hass = getattr(self, "hass", None)
        if hass is None:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="remote_infrared_missing",
                translation_placeholders={"entity_id": entity_id},
            )

        try:
            await infrared.async_send_command(hass, entity_id, ir_command)
        except HomeAssistantError:
            raise
        except Exception as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="remote_send_failed",
                translation_placeholders={"error": str(err)},
            ) from err

    def _resolve_infrared_entity_id(self) -> str:
        """Return the configured backing infrared entity id."""
        hass = getattr(self, "hass", None)
        if hass is None:
            return self._infrared_entity_id

        state = hass.states.get(self._infrared_entity_id)
        if state is None or state.state == STATE_UNAVAILABLE:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="remote_infrared_missing",
                translation_placeholders={"entity_id": self._infrared_entity_id},
            )

        return self._infrared_entity_id
