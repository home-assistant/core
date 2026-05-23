"""Remote entities for virtual remotes backed by infrared entities."""

import asyncio
from collections.abc import Callable, Iterable, Mapping
import logging
from typing import Any

from homeassistant.components import infrared
from homeassistant.components.remote import RemoteEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant, callback
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback
from homeassistant.helpers.event import async_track_state_change_event

from .command import parse_remote_command as _parse_remote_command
from .const import (
    CONF_INFRARED_ENTITY_ID,
    CONF_REMOTE_COMMANDS,
    CONF_REMOTE_ID,
    CONF_REMOTE_NAME,
    CONF_VIRTUAL_REMOTES,
    DEFAULT_DELAY_SECS,
    DEFAULT_NUM_REPEATS,
    DOMAIN,
)
from .repairs import (
    async_create_linked_infrared_entity_missing_issue,
    async_delete_linked_infrared_entity_missing_issue,
    async_delete_stale_linked_infrared_entity_missing_issues,
)

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0

COMMAND_POWER_ON = "POWER_ON"
COMMAND_POWER_OFF = "POWER_OFF"
COMMAND_TOGGLE = "TOGGLE"
COMMAND_POWER_TOGGLE = "POWER_TOGGLE"

type DeviceInfoFactory = Callable[[str, str, Mapping[str, Any]], DeviceInfo]
type EntityNameFactory = Callable[[str, str, Mapping[str, Any]], str | None]
type MissingInfraredEntityIssueHandler = Callable[[HomeAssistant, str, str, str], None]
type RestoredInfraredEntityIssueHandler = Callable[[HomeAssistant, str], None]


def _as_str_mapping(value: Any) -> dict[str, str] | None:
    """Return valid string items from a mapping or None when not a mapping."""
    if not isinstance(value, Mapping):
        return None

    result: dict[str, str] = {}
    for key, item in value.items():
        if not isinstance(key, str) or not isinstance(item, str):
            _LOGGER.debug("Ignoring malformed virtual remote command entry")
            continue
        result[key] = item

    return result


def remote_unique_id(entry_id: str, remote_id: str) -> str:
    """Return the unique id for a configured virtual remote."""
    return f"{entry_id}_remote_{remote_id}"


def configured_remote_definitions(entry: ConfigEntry) -> list[Mapping[str, Any]]:
    """Return configured virtual remote definitions."""
    entry_data = getattr(entry, "data", {})
    configured_remotes = entry.options.get(
        CONF_VIRTUAL_REMOTES,
        entry_data.get(CONF_VIRTUAL_REMOTES, []),
    )

    if not isinstance(configured_remotes, list):
        _LOGGER.warning("Ignoring malformed virtual remote configuration")
        return []

    return [
        remote_config
        for remote_config in configured_remotes
        if isinstance(remote_config, Mapping)
    ]


def _virtual_remote_device_info(
    remote_id: str,
    name: str,
    remote_config: Mapping[str, Any],
) -> DeviceInfo:
    """Return device info for a standalone virtual remote."""
    return DeviceInfo(identifiers={(DOMAIN, remote_id)}, name=name)


def _standalone_virtual_remote_entity_name(
    remote_id: str,
    name: str,
    remote_config: Mapping[str, Any],
) -> str | None:
    """Return entity name for a standalone virtual remote.

    The standalone Virtual Remote integration creates one device per remote, so
    the remote entity is the primary feature of the device and should inherit
    the device name.
    """
    return None


def _create_missing_issue(
    hass: HomeAssistant,
    remote_id: str,
    remote_name: str,
    infrared_entity_id: str,
) -> None:
    """Create a standalone Virtual Remote missing infrared repair issue."""
    async_create_linked_infrared_entity_missing_issue(
        hass,
        remote_id=remote_id,
        remote_name=remote_name,
        infrared_entity_id=infrared_entity_id,
    )


def _delete_missing_issue(hass: HomeAssistant, remote_id: str) -> None:
    """Delete a standalone Virtual Remote missing infrared repair issue."""
    async_delete_linked_infrared_entity_missing_issue(hass, remote_id=remote_id)


@callback
def cleanup_stale_remote_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
    configured_remote_ids: set[str],
) -> None:
    """Remove stale remote entity registry entries for removed remotes.

    This cleanup is safe for both the standalone Virtual Remote integration and
    integrations such as iTach IP2IR which reuse the shared virtual remote
    entity implementation.
    """
    entity_registry = er.async_get(hass)
    expected_unique_ids = {
        remote_unique_id(entry.entry_id, remote_id)
        for remote_id in configured_remote_ids
    }
    unique_id_prefix = f"{entry.entry_id}_remote_"

    for entity_entry in er.async_entries_for_config_entry(
        entity_registry, entry.entry_id
    ):
        if entity_entry.domain != "remote":
            continue

        unique_id = entity_entry.unique_id
        if (
            unique_id.startswith(unique_id_prefix)
            and unique_id not in expected_unique_ids
        ):
            entity_registry.async_remove(entity_entry.entity_id)


@callback
def cleanup_stale_virtual_remote_devices(
    hass: HomeAssistant,
    entry: ConfigEntry,
    configured_remote_ids: set[str],
    *,
    identifier_domain: str = DOMAIN,
) -> None:
    """Remove stale virtual-remote device registry entries.

    This is intended for the standalone Virtual Remote integration where each
    virtual remote is represented as its own device. Do not use this for
    physical-device integrations which attach virtual remote entities to their
    real hardware device.
    """
    device_registry = dr.async_get(hass)

    for device_entry in list(device_registry.devices.values()):
        if entry.entry_id not in device_entry.config_entries:
            continue

        remote_identifiers = {
            identifier[1]
            for identifier in device_entry.identifiers
            if identifier[0] == identifier_domain
        }
        if remote_identifiers and remote_identifiers.isdisjoint(configured_remote_ids):
            device_registry.async_remove_device(device_entry.id)


@callback
def cleanup_stale_missing_infrared_issues(
    hass: HomeAssistant,
    configured_remote_ids: set[str],
    *,
    issue_cleanup_handler: RestoredInfraredEntityIssueHandler | None,
) -> None:
    """Clear repair issues for remote ids that are no longer configured."""
    if issue_cleanup_handler is not _delete_missing_issue:
        return

    async_delete_stale_linked_infrared_entity_missing_issues(
        hass, configured_remote_ids=configured_remote_ids
    )


async def async_setup_virtual_remote_entities(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
    *,
    device_info_factory: DeviceInfoFactory,
    entity_name_factory: EntityNameFactory | None = None,
    has_entity_name: bool = True,
    cleanup_devices: bool = False,
    device_identifier_domain: str = DOMAIN,
    translation_domain: str = DOMAIN,
    missing_infrared_issue_handler: MissingInfraredEntityIssueHandler | None = None,
    restored_infrared_issue_handler: RestoredInfraredEntityIssueHandler | None = None,
) -> None:
    """Set up configured virtual remote entities.

    Integrations which reuse this implementation should call this helper and
    provide factories appropriate for their device model.

    For a standalone helper integration where each remote is its own device,
    use ``has_entity_name=True`` and an entity name of ``None``. For physical
    device integrations such as iTach IP2IR, use ``has_entity_name=False`` and
    return the configured virtual remote name from ``entity_name_factory`` so
    entities do not inherit the physical hardware device name.
    """
    if entity_name_factory is None:
        entity_name_factory = _standalone_virtual_remote_entity_name

    entities: list[InfraredRemoteEntity] = []
    configured_remote_ids: set[str] = set()
    for remote_config in configured_remote_definitions(entry):
        remote_id = remote_config.get(CONF_REMOTE_ID)
        name = remote_config.get(CONF_REMOTE_NAME)
        infrared_entity_id = remote_config.get(CONF_INFRARED_ENTITY_ID)
        commands = _as_str_mapping(remote_config.get(CONF_REMOTE_COMMANDS, {}))

        if (
            not isinstance(remote_id, str)
            or not remote_id
            or not isinstance(name, str)
            or not name
            or not isinstance(infrared_entity_id, str)
            or not infrared_entity_id
            or commands is None
        ):
            _LOGGER.debug("Skipping malformed virtual remote entry")
            continue

        if remote_id in configured_remote_ids:
            _LOGGER.debug("Skipping duplicate virtual remote id: %s", remote_id)
            continue

        configured_remote_ids.add(remote_id)
        entities.append(
            InfraredRemoteEntity(
                remote_id=remote_id,
                name=name,
                infrared_entity_id=infrared_entity_id,
                commands=commands,
                unique_id_prefix=entry.entry_id,
                device_info=device_info_factory(remote_id, name, remote_config),
                entity_name=entity_name_factory(remote_id, name, remote_config),
                has_entity_name=has_entity_name,
                translation_domain=translation_domain,
                missing_infrared_issue_handler=missing_infrared_issue_handler,
                restored_infrared_issue_handler=restored_infrared_issue_handler,
            )
        )

    cleanup_stale_remote_entities(hass, entry, configured_remote_ids)
    cleanup_stale_missing_infrared_issues(
        hass,
        configured_remote_ids,
        issue_cleanup_handler=restored_infrared_issue_handler,
    )

    if cleanup_devices:
        cleanup_stale_virtual_remote_devices(
            hass,
            entry,
            configured_remote_ids,
            identifier_domain=device_identifier_domain,
        )

    async_add_entities(entities)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up configured virtual remote entities."""
    await async_setup_virtual_remote_entities(
        hass,
        entry,
        async_add_entities,
        device_info_factory=_virtual_remote_device_info,
        entity_name_factory=_standalone_virtual_remote_entity_name,
        has_entity_name=True,
        cleanup_devices=True,
        missing_infrared_issue_handler=_create_missing_issue,
        restored_infrared_issue_handler=_delete_missing_issue,
    )


class InfraredRemoteEntity(RemoteEntity):
    """Virtual remote backed by a Home Assistant infrared entity."""

    _attr_has_entity_name = True
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
        entity_name: str | None,
        has_entity_name: bool,
        translation_domain: str = DOMAIN,
        missing_infrared_issue_handler: MissingInfraredEntityIssueHandler | None = None,
        restored_infrared_issue_handler: RestoredInfraredEntityIssueHandler
        | None = None,
    ) -> None:
        """Initialize the virtual remote."""
        self._remote_id = remote_id
        self._remote_name = name
        self._attr_name = entity_name
        self._attr_has_entity_name = has_entity_name
        self._attr_unique_id = remote_unique_id(unique_id_prefix, remote_id)
        self._attr_device_info = device_info
        self._infrared_entity_id = infrared_entity_id
        self._commands = commands or {}
        self._translation_domain = translation_domain
        self._missing_infrared_issue_handler = missing_infrared_issue_handler
        self._restored_infrared_issue_handler = restored_infrared_issue_handler
        self._last_available: bool | None = None
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
        return state is not None and state.state != STATE_UNAVAILABLE

    async def async_added_to_hass(self) -> None:
        """Handle entity added to Home Assistant."""

        @callback
        def _handle_infrared_state_change(event: Any) -> None:
            """Handle linked infrared entity state changes."""
            self._update_missing_infrared_repair_issue()
            self.async_write_ha_state()

        self.async_on_remove(
            async_track_state_change_event(
                self.hass,
                [self._infrared_entity_id],
                _handle_infrared_state_change,
            )
        )
        self._update_missing_infrared_repair_issue()

    async def async_update(self) -> None:
        """Update repair state for the linked infrared entity."""
        self._update_missing_infrared_repair_issue()

    async def async_turn_on(self, **kwargs: Any) -> None:
        """Turn on the virtual remote."""
        if not self._has_configured_command(COMMAND_POWER_ON):
            return

        await self._async_send_named_command(COMMAND_POWER_ON, kwargs)
        self._is_on = True
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        """Turn off the virtual remote."""
        if not self._has_configured_command(COMMAND_POWER_OFF):
            return

        await self._async_send_named_command(COMMAND_POWER_OFF, kwargs)
        self._is_on = False
        self.async_write_ha_state()

    async def async_toggle(self, **kwargs: Any) -> None:
        """Toggle the virtual remote."""
        command = None
        if self._has_configured_command(COMMAND_TOGGLE):
            command = COMMAND_TOGGLE
        elif self._has_configured_command(COMMAND_POWER_TOGGLE):
            command = COMMAND_POWER_TOGGLE

        if command is None:
            return

        await self._async_send_named_command(command, kwargs)
        self._is_on = not self._is_on
        self.async_write_ha_state()

    async def async_send_command(self, command: Iterable[str], **kwargs: Any) -> None:
        """Send one or more commands through the backing infrared entity."""
        self._update_missing_infrared_repair_issue()

        num_repeats = kwargs.pop("num_repeats", DEFAULT_NUM_REPEATS)
        delay_secs = kwargs.pop("delay_secs", DEFAULT_DELAY_SECS)

        if (
            not isinstance(num_repeats, int)
            or isinstance(num_repeats, bool)
            or num_repeats < 1
        ):
            raise HomeAssistantError(
                translation_domain=self._translation_domain,
                translation_key="remote_invalid_service_parameter",
                translation_placeholders={
                    "error": "num_repeats must be a positive integer"
                },
            )

        if (
            not isinstance(delay_secs, (int, float))
            or isinstance(delay_secs, bool)
            or delay_secs < 0
        ):
            raise HomeAssistantError(
                translation_domain=self._translation_domain,
                translation_key="remote_invalid_service_parameter",
                translation_placeholders={
                    "error": "delay_secs must be a non-negative number"
                },
            )

        try:
            commands = [command] if isinstance(command, str) else list(command)
        except TypeError as err:
            raise HomeAssistantError(
                translation_domain=self._translation_domain,
                translation_key="remote_invalid_service_parameter",
                translation_placeholders={
                    "error": "command must be a string or list of strings"
                },
            ) from err

        if not all(isinstance(item, str) for item in commands):
            raise HomeAssistantError(
                translation_domain=self._translation_domain,
                translation_key="remote_invalid_service_parameter",
                translation_placeholders={"error": "command must be a string"},
            )

        total = len(commands) * num_repeats
        sent = 0

        for _ in range(num_repeats):
            for item in commands:
                await self._async_send_named_command(item, kwargs)
                sent += 1

                if delay_secs and sent < total:
                    await asyncio.sleep(delay_secs)

    def _configured_command_payload(self, command: str) -> str | None:
        """Return configured command payload using case-insensitive command names."""
        if command in self._commands:
            return self._commands[command]

        normalized_command = command.upper()
        for configured_command, payload in self._commands.items():
            if configured_command.upper() == normalized_command:
                return payload

        return None

    def _has_configured_command(self, command: str) -> bool:
        """Return whether a configured command exists."""
        return self._configured_command_payload(command) is not None

    async def _async_send_named_command(
        self,
        command: str,
        kwargs: dict[str, Any] | None = None,
    ) -> None:
        """Resolve and send a named or raw infrared command."""
        configured_payload = self._configured_command_payload(command)
        if configured_payload is not None:
            command_is_configured = True
            raw_command = configured_payload
        else:
            command_is_configured = False
            raw_command = command

        try:
            ir_command = _parse_remote_command(
                raw_command,
                kwargs or {},
                translation_domain=self._translation_domain,
            )
        except HomeAssistantError as err:
            looks_like_named_command = (
                not command_is_configured
                and bool(command)
                and " " not in command
                and all(char.isalnum() or char in {"_", "-"} for char in command)
            )
            if looks_like_named_command:
                raise HomeAssistantError(
                    translation_domain=self._translation_domain,
                    translation_key="remote_command_missing",
                    translation_placeholders={"command": command},
                ) from err
            raise

        entity_id = self._resolve_infrared_entity_id()

        hass = getattr(self, "hass", None)
        if hass is None:
            raise HomeAssistantError(
                translation_domain=self._translation_domain,
                translation_key="remote_infrared_missing",
                translation_placeholders={"entity_id": entity_id},
            )

        try:
            await infrared.async_send_command(hass, entity_id, ir_command)
        except HomeAssistantError:
            raise
        except Exception as err:
            raise HomeAssistantError(
                translation_domain=self._translation_domain,
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
            self._update_missing_infrared_repair_issue()
            raise HomeAssistantError(
                translation_domain=self._translation_domain,
                translation_key="remote_infrared_missing",
                translation_placeholders={"entity_id": self._infrared_entity_id},
            )

        self._update_missing_infrared_repair_issue()
        return self._infrared_entity_id

    @callback
    def _update_missing_infrared_repair_issue(self) -> None:
        """Create or clear a repair issue for the linked infrared entity."""
        hass = getattr(self, "hass", None)
        if hass is None:
            return

        is_available = self.available
        if self._last_available is is_available:
            return

        self._last_available = is_available

        if is_available:
            if self._restored_infrared_issue_handler is not None:
                self._restored_infrared_issue_handler(hass, self._remote_id)
            return

        if self._missing_infrared_issue_handler is not None:
            self._missing_infrared_issue_handler(
                hass,
                self._remote_id,
                self._remote_name,
                self._infrared_entity_id,
            )
