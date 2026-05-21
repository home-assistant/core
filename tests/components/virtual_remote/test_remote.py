"""Tests for virtual remote entities."""

from __future__ import annotations

from collections.abc import Mapping
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo

from homeassistant.components.virtual_remote.const import (
    CONF_INFRARED_ENTITY_ID,
    CONF_REMOTE_COMMANDS,
    CONF_REMOTE_ID,
    CONF_REMOTE_NAME,
    CONF_VIRTUAL_REMOTES,
    DOMAIN,
)
from homeassistant.components.virtual_remote.remote import (
    COMMAND_POWER_OFF,
    COMMAND_POWER_ON,
    COMMAND_POWER_TOGGLE,
    COMMAND_TOGGLE,
    InfraredRemoteEntity,
    async_setup_entry,
    async_setup_virtual_remote_entities,
    cleanup_stale_remote_entities,
    cleanup_stale_virtual_remote_devices,
    configured_remote_definitions,
    remote_unique_id,
)

from tests.common import MockConfigEntry

from .conftest import INFRARED_ENTITY_ID, RAW_COMMAND, REMOTE_ID, REMOTE_NAME


def _device_info_factory(
    remote_id: str,
    name: str,
    remote_config: Mapping[str, object],
) -> DeviceInfo:
    """Return device info for tests."""
    return DeviceInfo(identifiers={(DOMAIN, remote_id)}, name=name)


def _entity_name_factory(
    remote_id: str,
    name: str,
    remote_config: Mapping[str, object],
) -> str:
    """Return entity name for tests."""
    return name


def _make_entity(
    hass: HomeAssistant,
    *,
    commands: dict[str, str] | None = None,
    infrared_entity_id: str = INFRARED_ENTITY_ID,
    missing_handler=None,
    restored_handler=None,
) -> InfraredRemoteEntity:
    """Create a remote entity for direct tests."""
    entity = InfraredRemoteEntity(
        remote_id=REMOTE_ID,
        name=REMOTE_NAME,
        infrared_entity_id=infrared_entity_id,
        commands=commands or {},
        unique_id_prefix="entry",
        device_info=DeviceInfo(identifiers={(DOMAIN, REMOTE_ID)}, name=REMOTE_NAME),
        entity_name=REMOTE_NAME,
        has_entity_name=False,
        translation_domain=DOMAIN,
        missing_infrared_issue_handler=missing_handler,
        restored_infrared_issue_handler=restored_handler,
    )
    entity.hass = hass
    return entity


def test_remote_unique_id() -> None:
    """Test remote unique id helper."""
    assert remote_unique_id("entry", "remote") == "entry_remote_remote"


def test_configured_remote_definitions(config_entry: MockConfigEntry) -> None:
    """Test configured remote definition helper."""
    assert configured_remote_definitions(config_entry) == config_entry.options[
        CONF_VIRTUAL_REMOTES
    ]

    config_entry.options[CONF_VIRTUAL_REMOTES] = "bad"
    assert configured_remote_definitions(config_entry) == []


async def test_async_setup_entry_adds_entities(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test standalone platform setup creates entities."""
    entities = []

    await async_setup_entry(hass, config_entry, entities.extend)

    assert len(entities) == 1
    entity = entities[0]
    assert entity.unique_id == f"{config_entry.entry_id}_remote_{REMOTE_ID}"
    assert entity.name == REMOTE_NAME


async def test_async_setup_virtual_remote_entities_shared_options(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test shared setup helper supports custom integration boundary."""
    entities = []
    missing_handler = Mock()
    restored_handler = Mock()

    await async_setup_virtual_remote_entities(
        hass,
        config_entry,
        entities.extend,
        device_info_factory=_device_info_factory,
        entity_name_factory=_entity_name_factory,
        has_entity_name=False,
        cleanup_devices=False,
        translation_domain="itachip2ir",
        missing_infrared_issue_handler=missing_handler,
        restored_infrared_issue_handler=restored_handler,
    )

    assert len(entities) == 1
    entity = entities[0]
    assert entity.name == REMOTE_NAME
    assert entity._translation_domain == "itachip2ir"


async def test_async_setup_skips_malformed_and_duplicate_remotes(
    hass: HomeAssistant,
    infrared_entity: str,
) -> None:
    """Test malformed remote entries are skipped."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            CONF_VIRTUAL_REMOTES: [
                {
                    CONF_REMOTE_ID: "valid",
                    CONF_REMOTE_NAME: "Valid",
                    CONF_INFRARED_ENTITY_ID: infrared_entity,
                },
                {
                    CONF_REMOTE_ID: "valid",
                    CONF_REMOTE_NAME: "Duplicate",
                    CONF_INFRARED_ENTITY_ID: infrared_entity,
                },
                {
                    CONF_REMOTE_ID: "bad",
                    CONF_REMOTE_NAME: "Bad",
                    CONF_INFRARED_ENTITY_ID: infrared_entity,
                    CONF_REMOTE_COMMANDS: {"POWER": 1},
                },
                "bad",
            ]
        },
    )
    entry.add_to_hass(hass)
    entities = []

    await async_setup_virtual_remote_entities(
        hass,
        entry,
        entities.extend,
        device_info_factory=_device_info_factory,
    )

    assert [entity.unique_id for entity in entities] == [
        f"{entry.entry_id}_remote_valid"
    ]


async def test_cleanup_stale_remote_entities(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test stale remote entity cleanup."""
    registry = er.async_get(hass)
    stale = registry.async_get_or_create(
        "remote",
        DOMAIN,
        "stale",
        suggested_object_id="stale",
        config_entry=config_entry,
    )
    stale.unique_id = f"{config_entry.entry_id}_remote_stale"
    keep = registry.async_get_or_create(
        "remote",
        DOMAIN,
        "keep",
        suggested_object_id="keep",
        config_entry=config_entry,
    )
    keep.unique_id = f"{config_entry.entry_id}_remote_keep"

    cleanup_stale_remote_entities(hass, config_entry, {"keep"})

    assert registry.async_get(stale.entity_id) is None
    assert registry.async_get(keep.entity_id) is not None


async def test_cleanup_stale_virtual_remote_devices(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test stale virtual remote device cleanup."""
    registry = dr.async_get(hass)
    stale = registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "stale")},
    )
    keep = registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "keep")},
    )
    physical = registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={("itachip2ir", "physical")},
    )

    cleanup_stale_virtual_remote_devices(hass, config_entry, {"keep"})

    assert registry.async_get(stale.id) is None
    assert registry.async_get(keep.id) is not None
    assert registry.async_get(physical.id) is not None


def test_available_property(hass: HomeAssistant, infrared_entity: str) -> None:
    """Test availability follows backing infrared entity."""
    entity = _make_entity(hass)

    assert entity.available is True

    hass.states.async_set(INFRARED_ENTITY_ID, STATE_UNAVAILABLE)
    assert entity.available is False

    hass.states.async_remove(INFRARED_ENTITY_ID)
    assert entity.available is False


async def test_power_methods_send_configured_commands(
    hass: HomeAssistant,
    infrared_entity: str,
) -> None:
    """Test turn on/off/toggle services."""
    entity = _make_entity(
        hass,
        commands={
            COMMAND_POWER_ON: RAW_COMMAND,
            COMMAND_POWER_OFF: RAW_COMMAND,
            COMMAND_TOGGLE: RAW_COMMAND,
        },
    )

    with patch(
        "homeassistant.components.virtual_remote.remote.infrared.async_send_command",
        AsyncMock(),
    ) as mock_send:
        await entity.async_turn_on()
        await entity.async_turn_off()
        await entity.async_toggle()

    assert len(mock_send.mock_calls) == 3
    assert entity.is_on is True


async def test_toggle_uses_power_toggle_fallback(
    hass: HomeAssistant,
    infrared_entity: str,
) -> None:
    """Test toggle falls back to POWER_TOGGLE."""
    entity = _make_entity(hass, commands={COMMAND_POWER_TOGGLE: RAW_COMMAND})

    with patch(
        "homeassistant.components.virtual_remote.remote.infrared.async_send_command",
        AsyncMock(),
    ) as mock_send:
        await entity.async_toggle()

    assert len(mock_send.mock_calls) == 1
    assert entity.is_on is False


async def test_power_methods_no_configured_command_noop(
    hass: HomeAssistant,
    infrared_entity: str,
) -> None:
    """Test power methods no-op without configured commands."""
    entity = _make_entity(hass)

    with patch(
        "homeassistant.components.virtual_remote.remote.infrared.async_send_command",
        AsyncMock(),
    ) as mock_send:
        await entity.async_turn_on()
        await entity.async_turn_off()
        await entity.async_toggle()

    assert len(mock_send.mock_calls) == 0
    assert entity.is_on is True


async def test_send_command_named_raw_repeat_and_delay(
    hass: HomeAssistant,
    infrared_entity: str,
) -> None:
    """Test send command supports named/raw, repeat, and delay."""
    entity = _make_entity(hass, commands={"POWER": RAW_COMMAND})

    with (
        patch(
            "homeassistant.components.virtual_remote.remote.infrared.async_send_command",
            AsyncMock(),
        ) as mock_send,
        patch("homeassistant.components.virtual_remote.remote.asyncio.sleep", AsyncMock()) as mock_sleep,
    ):
        await entity.async_send_command(
            ["power", RAW_COMMAND],
            num_repeats=2,
            delay_secs=0.5,
        )

    assert len(mock_send.mock_calls) == 4
    assert len(mock_sleep.mock_calls) == 3


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"num_repeats": 0}, "num_repeats"),
        ({"num_repeats": "bad"}, "num_repeats"),
        ({"delay_secs": -1}, "delay_secs"),
        ({"delay_secs": "bad"}, "delay_secs"),
    ],
)
async def test_send_command_invalid_service_parameters(
    hass: HomeAssistant,
    infrared_entity: str,
    kwargs: dict,
    message: str,
) -> None:
    """Test invalid remote.send_command parameters."""
    entity = _make_entity(hass)

    with pytest.raises(HomeAssistantError) as err:
        await entity.async_send_command([RAW_COMMAND], **kwargs)

    assert err.value.translation_key == "remote_invalid_service_parameter"
    assert message in err.value.translation_placeholders["error"]


async def test_send_command_non_string_command(
    hass: HomeAssistant,
    infrared_entity: str,
) -> None:
    """Test non-string command raises."""
    entity = _make_entity(hass)

    with pytest.raises(HomeAssistantError) as err:
        await entity.async_send_command([1])  # type: ignore[list-item]

    assert err.value.translation_key == "remote_invalid_service_parameter"


async def test_missing_named_command_error(
    hass: HomeAssistant,
    infrared_entity: str,
) -> None:
    """Test missing named command error."""
    entity = _make_entity(hass)

    with pytest.raises(HomeAssistantError) as err:
        await entity.async_send_command(["POWER"])

    assert err.value.translation_key == "remote_command_missing"
    assert err.value.translation_placeholders == {"command": "POWER"}


async def test_invalid_raw_command_error(
    hass: HomeAssistant,
    infrared_entity: str,
) -> None:
    """Test invalid raw command preserves parser error."""
    entity = _make_entity(hass)

    with pytest.raises(HomeAssistantError) as err:
        await entity.async_send_command([""])

    assert err.value.translation_key == "remote_invalid_command"


async def test_missing_infrared_entity_error_and_repair_issue(
    hass: HomeAssistant,
) -> None:
    """Test missing backing infrared entity creates repair issue."""
    missing_handler = Mock()
    restored_handler = Mock()
    entity = _make_entity(
        hass,
        commands={"POWER": RAW_COMMAND},
        missing_handler=missing_handler,
        restored_handler=restored_handler,
    )

    await entity.async_added_to_hass()
    missing_handler.assert_called_once_with(
        hass,
        REMOTE_ID,
        REMOTE_NAME,
        INFRARED_ENTITY_ID,
    )

    with pytest.raises(HomeAssistantError) as err:
        await entity.async_send_command(["POWER"])

    assert err.value.translation_key == "remote_infrared_missing"


async def test_repair_issue_cleared_when_entity_restored(
    hass: HomeAssistant,
    infrared_entity: str,
) -> None:
    """Test repair issue cleared when backing entity is restored."""
    missing_handler = Mock()
    restored_handler = Mock()
    entity = _make_entity(
        hass,
        missing_handler=missing_handler,
        restored_handler=restored_handler,
    )

    await entity.async_added_to_hass()

    restored_handler.assert_called_once_with(hass, REMOTE_ID)
    missing_handler.assert_not_called()


async def test_send_failure_wrapped(
    hass: HomeAssistant,
    infrared_entity: str,
) -> None:
    """Test unexpected infrared send errors are wrapped."""
    entity = _make_entity(hass, commands={"POWER": RAW_COMMAND})

    with patch(
        "homeassistant.components.virtual_remote.remote.infrared.async_send_command",
        AsyncMock(side_effect=RuntimeError("boom")),
    ):
        with pytest.raises(HomeAssistantError) as err:
            await entity.async_send_command(["POWER"])

    assert err.value.translation_key == "remote_send_failed"
    assert err.value.translation_placeholders == {"error": "boom"}
