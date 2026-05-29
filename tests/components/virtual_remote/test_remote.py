"""Tests for virtual remote entities."""

from collections.abc import Iterable, Mapping
from typing import Any, cast
from unittest.mock import AsyncMock, Mock, patch

import pytest

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
    _as_str_mapping,
    _create_missing_issue,
    _delete_missing_issue,
    _virtual_remote_device_info,
    async_setup_virtual_remote_entities,
    cleanup_stale_missing_infrared_issues,
    cleanup_stale_remote_entities,
    cleanup_stale_virtual_remote_devices,
    configured_remote_definitions,
    remote_unique_id,
)
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from .conftest import INFRARED_ENTITY_ID, RAW_COMMAND, REMOTE_ID, REMOTE_NAME

from tests.common import MockConfigEntry


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


def _add_remote_entities_callback(
    entities: list[InfraredRemoteEntity],
) -> AddConfigEntryEntitiesCallback:
    """Return an add-entities callback that captures remote entities."""

    def _add_entities(
        new_entities: Iterable[Entity],
        update_before_add: bool = False,
        *,
        config_subentry_id: str | None = None,
    ) -> None:
        entities.extend(cast(Iterable[InfraredRemoteEntity], new_entities))

    return _add_entities


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


def test_as_str_mapping_filters_invalid_entries() -> None:
    """Test invalid command entries are dropped without rejecting the mapping."""
    assert _as_str_mapping("bad") is None
    assert _as_str_mapping({"POWER": RAW_COMMAND, "BAD": 1, 2: RAW_COMMAND}) == {
        "POWER": RAW_COMMAND
    }


def test_standalone_repair_issue_helpers(hass: HomeAssistant) -> None:
    """Test standalone repair issue helper boundaries."""
    with patch(
        "homeassistant.components.virtual_remote.remote."
        "async_create_linked_infrared_entity_missing_issue"
    ) as create_issue:
        _create_missing_issue(hass, REMOTE_ID, REMOTE_NAME, INFRARED_ENTITY_ID)

    create_issue.assert_called_once_with(
        hass,
        remote_id=REMOTE_ID,
        remote_name=REMOTE_NAME,
        infrared_entity_id=INFRARED_ENTITY_ID,
    )

    with patch(
        "homeassistant.components.virtual_remote.remote."
        "async_delete_linked_infrared_entity_missing_issue"
    ) as delete_issue:
        _delete_missing_issue(hass, REMOTE_ID)

    delete_issue.assert_called_once_with(hass, remote_id=REMOTE_ID)


def test_configured_remote_definitions(config_entry: MockConfigEntry) -> None:
    """Test configured remote definition helper."""
    assert (
        configured_remote_definitions(config_entry)
        == config_entry.options[CONF_VIRTUAL_REMOTES]
    )

    bad_entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={CONF_VIRTUAL_REMOTES: "bad"},
    )
    assert configured_remote_definitions(bad_entry) == []


async def test_async_setup_entry_adds_entities(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test standalone platform setup creates entities."""
    entities: list[InfraredRemoteEntity] = []

    await async_setup_virtual_remote_entities(
        hass,
        config_entry,
        _add_remote_entities_callback(entities),
        device_info_factory=_device_info_factory,
    )

    assert len(entities) == 1
    entity = entities[0]
    assert entity.unique_id == f"{config_entry.entry_id}_remote_{REMOTE_ID}"
    assert entity.name is None
    assert entity.device_info == DeviceInfo(
        identifiers={(DOMAIN, REMOTE_ID)},
        name=REMOTE_NAME,
    )


async def test_async_setup_virtual_remote_entities_shared_options(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test shared setup helper supports custom integration boundary."""
    entities: list[InfraredRemoteEntity] = []
    missing_handler = Mock()
    restored_handler = Mock()

    await async_setup_virtual_remote_entities(
        hass,
        config_entry,
        _add_remote_entities_callback(entities),
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
    entities: list[InfraredRemoteEntity] = []

    await async_setup_virtual_remote_entities(
        hass,
        entry,
        _add_remote_entities_callback(entities),
        device_info_factory=_device_info_factory,
    )

    assert [entity.unique_id for entity in entities] == [
        f"{entry.entry_id}_remote_valid",
        f"{entry.entry_id}_remote_bad",
    ]


async def test_async_setup_keeps_remote_with_invalid_command_entries(
    hass: HomeAssistant,
    infrared_entity: str,
) -> None:
    """Test invalid command entries do not drop an otherwise valid remote."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={},
        options={
            CONF_VIRTUAL_REMOTES: [
                {
                    CONF_REMOTE_ID: "valid",
                    CONF_REMOTE_NAME: "Valid",
                    CONF_INFRARED_ENTITY_ID: infrared_entity,
                    CONF_REMOTE_COMMANDS: {"POWER": RAW_COMMAND, "BAD": 1},
                },
                {
                    CONF_REMOTE_ID: "bad_commands",
                    CONF_REMOTE_NAME: "Bad commands",
                    CONF_INFRARED_ENTITY_ID: infrared_entity,
                    CONF_REMOTE_COMMANDS: "bad",
                },
            ]
        },
    )
    entry.add_to_hass(hass)
    entities: list[InfraredRemoteEntity] = []

    await async_setup_virtual_remote_entities(
        hass,
        entry,
        _add_remote_entities_callback(entities),
        device_info_factory=_device_info_factory,
    )

    assert [entity.unique_id for entity in entities] == [
        f"{entry.entry_id}_remote_valid",
        f"{entry.entry_id}_remote_bad_commands",
    ]
    assert entities[1]._commands == {}
    assert entities[0]._commands == {"POWER": RAW_COMMAND}


async def test_cleanup_stale_remote_entities(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test stale remote entity cleanup."""
    registry = er.async_get(hass)
    stale = registry.async_get_or_create(
        "remote",
        DOMAIN,
        f"{config_entry.entry_id}_remote_stale",
        suggested_object_id="stale",
        config_entry=config_entry,
    )
    keep = registry.async_get_or_create(
        "remote",
        DOMAIN,
        f"{config_entry.entry_id}_remote_keep",
        suggested_object_id="keep",
        config_entry=config_entry,
    )

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


async def test_cleanup_stale_remote_entities_ignores_other_domains(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test stale remote cleanup ignores non-remote entity registry entries."""
    registry = er.async_get(hass)
    sensor = registry.async_get_or_create(
        "sensor",
        DOMAIN,
        f"{config_entry.entry_id}_remote_stale",
        suggested_object_id="stale_sensor",
        config_entry=config_entry,
    )

    cleanup_stale_remote_entities(hass, config_entry, set())

    assert registry.async_get(sensor.entity_id) is not None


async def test_cleanup_stale_virtual_remote_devices_ignores_other_config_entries(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test device cleanup ignores devices from other config entries."""
    registry = dr.async_get(hass)

    other_entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="other_entry",
    )
    other_entry.add_to_hass(hass)

    other = registry.async_get_or_create(
        config_entry_id=other_entry.entry_id,
        identifiers={(DOMAIN, "stale")},
    )

    cleanup_stale_virtual_remote_devices(hass, config_entry, set())

    assert registry.async_get(other.id) is not None


def test_available_property(hass: HomeAssistant, infrared_entity: str) -> None:
    """Test availability follows backing infrared entity."""
    entity = _make_entity(hass)

    assert entity.available is True

    hass.states.async_set(INFRARED_ENTITY_ID, STATE_UNAVAILABLE)
    assert entity.available is False

    hass.states.async_remove(INFRARED_ENTITY_ID)
    assert entity.available is False


def test_available_without_hass_returns_true() -> None:
    """Test entity is considered available before being added to Home Assistant."""
    entity = InfraredRemoteEntity(
        remote_id=REMOTE_ID,
        name=REMOTE_NAME,
        infrared_entity_id=INFRARED_ENTITY_ID,
        commands={},
        unique_id_prefix="entry",
        device_info=DeviceInfo(identifiers={(DOMAIN, REMOTE_ID)}, name=REMOTE_NAME),
        entity_name=REMOTE_NAME,
        has_entity_name=False,
    )

    assert entity.available is True
    assert entity._resolve_infrared_entity_id() == INFRARED_ENTITY_ID
    entity._update_missing_infrared_repair_issue()


async def test_infrared_state_change_updates_repair_issue_and_state(
    hass: HomeAssistant,
    infrared_entity: str,
) -> None:
    """Test linked infrared state changes update repairs and entity state."""
    missing_handler = Mock()
    restored_handler = Mock()
    entity = _make_entity(
        hass,
        missing_handler=missing_handler,
        restored_handler=restored_handler,
    )

    with patch.object(entity, "async_write_ha_state") as write_state:
        await entity.async_added_to_hass()
        hass.states.async_set(INFRARED_ENTITY_ID, STATE_UNAVAILABLE)
        await hass.async_block_till_done()

    restored_handler.assert_called_once_with(hass, REMOTE_ID)
    missing_handler.assert_called_once_with(
        hass,
        REMOTE_ID,
        REMOTE_NAME,
        INFRARED_ENTITY_ID,
    )
    write_state.assert_called_once()


async def test_async_update_refreshes_repair_issue(
    hass: HomeAssistant,
    infrared_entity: str,
) -> None:
    """Test async update refreshes repair issue state."""
    restored_handler = Mock()
    entity = _make_entity(hass, restored_handler=restored_handler)

    await entity.async_update()

    restored_handler.assert_called_once_with(hass, REMOTE_ID)


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

    with (
        patch(
            "homeassistant.components.virtual_remote.remote.infrared.async_send_command",
            AsyncMock(),
        ) as mock_send,
        patch.object(entity, "async_write_ha_state"),
    ):
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

    with (
        patch(
            "homeassistant.components.virtual_remote.remote.infrared.async_send_command",
            AsyncMock(),
        ) as mock_send,
        patch.object(entity, "async_write_ha_state"),
    ):
        await entity.async_toggle()

    assert len(mock_send.mock_calls) == 1
    assert entity.is_on is False


async def test_power_methods_no_configured_command_noop(
    hass: HomeAssistant,
    infrared_entity: str,
) -> None:
    """Test power methods no-op without configured commands."""
    entity = _make_entity(hass)

    with (
        patch(
            "homeassistant.components.virtual_remote.remote.infrared.async_send_command",
            AsyncMock(),
        ) as mock_send,
        patch.object(entity, "async_write_ha_state"),
    ):
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
        patch(
            "homeassistant.components.virtual_remote.remote.asyncio.sleep", AsyncMock()
        ) as mock_sleep,
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
        ({"num_repeats": True}, "num_repeats"),
        ({"num_repeats": "bad"}, "num_repeats"),
        ({"delay_secs": -1}, "delay_secs"),
        ({"delay_secs": True}, "delay_secs"),
        ({"delay_secs": "bad"}, "delay_secs"),
    ],
)
async def test_send_command_invalid_service_parameters(
    hass: HomeAssistant,
    infrared_entity: str,
    kwargs: dict[str, Any],
    message: str,
) -> None:
    """Test invalid remote.send_command parameters."""
    entity = _make_entity(hass)

    with pytest.raises(HomeAssistantError) as err:
        await entity.async_send_command([RAW_COMMAND], **kwargs)

    assert err.value.translation_key == "remote_invalid_service_parameter"
    assert err.value.translation_placeholders is not None
    assert message in err.value.translation_placeholders["error"]


async def test_send_command_non_string_command(
    hass: HomeAssistant,
    infrared_entity: str,
) -> None:
    """Test non-string command raises before sending anything."""
    entity = _make_entity(hass)

    with (
        patch(
            "homeassistant.components.virtual_remote.remote.infrared.async_send_command",
            AsyncMock(),
        ) as mock_send,
        pytest.raises(HomeAssistantError) as err,
    ):
        await entity.async_send_command([RAW_COMMAND, 1])  # type: ignore[list-item]

    assert err.value.translation_key == "remote_invalid_service_parameter"
    assert err.value.translation_placeholders == {
        "error": "command must be a string or list of strings"
    }
    assert len(mock_send.mock_calls) == 0


async def test_send_command_non_iterable_command(
    hass: HomeAssistant,
    infrared_entity: str,
) -> None:
    """Test non-iterable command raises a translated error."""
    entity = _make_entity(hass)

    with pytest.raises(HomeAssistantError) as err:
        await entity.async_send_command(1)  # type: ignore[arg-type]

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


async def test_send_command_without_hass_raises_missing_infrared() -> None:
    """Test sending before entity is added raises a translated error."""
    entity = InfraredRemoteEntity(
        remote_id=REMOTE_ID,
        name=REMOTE_NAME,
        infrared_entity_id=INFRARED_ENTITY_ID,
        commands={"POWER": RAW_COMMAND},
        unique_id_prefix="entry",
        device_info=DeviceInfo(identifiers={(DOMAIN, REMOTE_ID)}, name=REMOTE_NAME),
        entity_name=REMOTE_NAME,
        has_entity_name=False,
    )

    with pytest.raises(HomeAssistantError) as err:
        await entity.async_send_command(["POWER"])

    assert err.value.translation_key == "remote_infrared_missing"


async def test_send_command_preserves_home_assistant_error(
    hass: HomeAssistant,
    infrared_entity: str,
) -> None:
    """Test HomeAssistantError raised by infrared send is preserved."""
    entity = _make_entity(hass, commands={"POWER": RAW_COMMAND})
    expected = HomeAssistantError("boom")

    with (
        patch(
            "homeassistant.components.virtual_remote.remote.infrared.async_send_command",
            AsyncMock(side_effect=expected),
        ),
        pytest.raises(HomeAssistantError) as err,
    ):
        await entity.async_send_command(["POWER"])

    assert err.value is expected


async def test_send_failure_wrapped(
    hass: HomeAssistant,
    infrared_entity: str,
) -> None:
    """Test unexpected infrared send errors are wrapped."""
    entity = _make_entity(hass, commands={"POWER": RAW_COMMAND})

    with (
        patch(
            "homeassistant.components.virtual_remote.remote.infrared.async_send_command",
            AsyncMock(side_effect=RuntimeError("boom")),
        ),
        pytest.raises(HomeAssistantError) as err,
    ):
        await entity.async_send_command(["POWER"])

    assert err.value.translation_key == "remote_send_failed"
    assert err.value.translation_placeholders == {"error": "boom"}


async def test_async_setup_entry_supports_single_entry_remote_data(
    hass: HomeAssistant,
    infrared_entity: str,
) -> None:
    """Test standalone setup supports one virtual remote per config entry storage."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="single_entry",
        data={
            CONF_REMOTE_ID: "tv",
            CONF_REMOTE_NAME: "TV",
            CONF_INFRARED_ENTITY_ID: infrared_entity,
        },
        options={CONF_REMOTE_COMMANDS: {COMMAND_POWER_ON: "38000:1,2"}},
    )
    entry.add_to_hass(hass)
    async_add_entities = Mock()

    await async_setup_virtual_remote_entities(
        hass,
        entry,
        async_add_entities,
        device_info_factory=_device_info_factory,
    )

    entities = async_add_entities.call_args.args[0]
    assert len(entities) == 1
    assert entities[0].unique_id == remote_unique_id(entry.entry_id, "tv")


async def test_async_setup_entry_ignores_malformed_single_entry_remote_data(
    hass: HomeAssistant,
    infrared_entity: str,
) -> None:
    """Test standalone setup ignores malformed one-remote entry data."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        entry_id="single_entry",
        data={
            CONF_REMOTE_ID: "tv",
            CONF_REMOTE_NAME: "",
            CONF_INFRARED_ENTITY_ID: infrared_entity,
        },
        options={},
    )
    entry.add_to_hass(hass)
    async_add_entities = Mock()

    await async_setup_virtual_remote_entities(
        hass,
        entry,
        async_add_entities,
        device_info_factory=_device_info_factory,
    )

    assert async_add_entities.call_args.args[0] == []


async def test_async_setup_virtual_remote_entities_skips_malformed_and_duplicate_remotes(
    hass: HomeAssistant,
    infrared_entity: str,
) -> None:
    """Test setup skips malformed and duplicate virtual remote definitions."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={})
    entry.add_to_hass(hass)
    entities: list[InfraredRemoteEntity] = []

    with patch(
        "homeassistant.components.virtual_remote.remote.configured_remote_definitions",
        return_value=[
            {
                CONF_REMOTE_ID: "valid",
                CONF_REMOTE_NAME: "Valid",
                CONF_INFRARED_ENTITY_ID: infrared_entity,
                CONF_REMOTE_COMMANDS: {COMMAND_POWER_ON: RAW_COMMAND},
            },
            {
                CONF_REMOTE_ID: "malformed",
                CONF_REMOTE_NAME: "",
                CONF_INFRARED_ENTITY_ID: infrared_entity,
            },
            {
                CONF_REMOTE_ID: "valid",
                CONF_REMOTE_NAME: "Duplicate",
                CONF_INFRARED_ENTITY_ID: infrared_entity,
            },
        ],
    ):
        await async_setup_virtual_remote_entities(
            hass,
            entry,
            _add_remote_entities_callback(entities),
            device_info_factory=_device_info_factory,
        )

    assert [entity.unique_id for entity in entities] == [
        f"{entry.entry_id}_remote_valid"
    ]


def test_virtual_remote_device_info_factory() -> None:
    """Test standalone virtual remote device info factory."""
    assert _virtual_remote_device_info("tv", "TV", {}) == DeviceInfo(
        identifiers={(DOMAIN, "tv")},
        name="TV",
    )


def test_cleanup_stale_missing_infrared_issues_uses_standalone_cleanup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test stale linked infrared repair issue cleanup for standalone remotes."""
    with patch(
        "homeassistant.components.virtual_remote.remote."
        "async_delete_stale_linked_infrared_entity_missing_issues"
    ) as delete_stale_issues:
        cleanup_stale_missing_infrared_issues(
            hass,
            {"living_room_tv"},
            issue_cleanup_handler=_delete_missing_issue,
        )

    delete_stale_issues.assert_called_once_with(
        hass, configured_remote_ids={"living_room_tv"}
    )


async def test_config_entry_setup_covers_standalone_remote_platform_setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test config entry setup reaches the standalone remote platform setup."""
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get("remote.living_room_tv") is not None


async def test_async_setup_virtual_remote_entities_runs_device_cleanup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test setup runs device cleanup when requested."""
    entities: list[InfraredRemoteEntity] = []

    with patch(
        "homeassistant.components.virtual_remote.remote."
        "cleanup_stale_virtual_remote_devices"
    ) as cleanup_devices:
        await async_setup_virtual_remote_entities(
            hass,
            config_entry,
            _add_remote_entities_callback(entities),
            device_info_factory=_device_info_factory,
            cleanup_devices=True,
        )

    cleanup_devices.assert_called_once_with(
        hass,
        config_entry,
        {"living_room_tv"},
        identifier_domain=DOMAIN,
    )
    assert len(entities) == 1
