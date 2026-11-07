"""Test the Mitsubishi WF-RAC setup, unload and migrations."""

from dataclasses import replace
from typing import Any
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from pywfrac import (
    WfRacAccountTableFullError,
    WfRacCommandError,
    WfRacConnectionError,
    WfRacError,
)

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.mitsubishi_wf_rac.const import (
    CONF_AIRCO_ID,
    CONF_CONNECTION_METHOD,
    CONF_OPERATOR_ID,
    DOMAIN,
)
from homeassistant.components.mitsubishi_wf_rac.coordinator import (
    registration_full_issue_id,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_DEVICE_ID,
    CONF_HOST,
    CONF_NAME,
    CONF_PORT,
    SERVICE_TURN_ON,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)

from . import AIRCO_ID, ENTRY_DATA, HOST, PORT, advance_polls

from tests.common import MockConfigEntry

ENTITY_ID = "climate.living_room"
LEGACY_UNIQUE_ID = f"{DOMAIN}-{AIRCO_ID}-climate"


def _legacy_entry(**overrides: Any) -> MockConfigEntry:
    """An entry as the custom component wrote it, before minor version 2."""
    return MockConfigEntry(
        **{
            "domain": DOMAIN,
            "title": "Living room",
            "data": ENTRY_DATA,
            "options": {},
            "unique_id": AIRCO_ID,
            "version": 8,
            **overrides,
        }
    )


async def test_setup_and_unload(
    hass: HomeAssistant, init_integration: MockConfigEntry
) -> None:
    """A reachable airco loads, and unloading releases the coordinator."""
    assert init_integration.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(init_integration.entry_id)
    await hass.async_block_till_done()
    assert init_integration.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    "error",
    [
        pytest.param(WfRacConnectionError("no route"), id="unreachable"),
        pytest.param(WfRacCommandError("refused"), id="refused"),
    ],
)
async def test_setup_retries_when_unreachable(
    hass: HomeAssistant,
    mock_repository: MagicMock,
    mock_config_entry: MockConfigEntry,
    error: WfRacError,
) -> None:
    """The first poll has no data to ride out a miss, so setup is retried."""
    mock_repository.async_get_status.side_effect = error
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert str(error) in mock_config_entry.reason


async def test_setup_registers_nothing(
    mock_repository: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Registering spends an account slot, and the config flow already did."""
    mock_repository.async_register.assert_not_awaited()


async def test_the_discovered_protocol_is_stored(
    init_integration: MockConfigEntry,
) -> None:
    """The next start skips protocol discovery."""
    assert init_integration.data[CONF_CONNECTION_METHOD] == "https"


async def test_a_stored_protocol_is_handed_to_the_library(
    hass: HomeAssistant, repository_class: MagicMock
) -> None:
    """The library client starts from the stored method and the HA time zone."""
    entry = _legacy_entry(
        data={**ENTRY_DATA, CONF_CONNECTION_METHOD: "https"}, minor_version=2
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    kwargs = repository_class.call_args.kwargs
    assert kwargs["method"] == "https"
    assert kwargs["time_zone"] == hass.config.time_zone
    assert entry.data[CONF_CONNECTION_METHOD] == "https"


@pytest.mark.usefixtures("hass")
async def test_device_registry_entry(
    init_integration: MockConfigEntry, device_registry: dr.DeviceRegistry
) -> None:
    """The airco registers with its MAC; ModelNr goes to model_id, not model."""
    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, AIRCO_ID), init_integration.entry_id
    )

    assert device is not None
    assert device.connections == {(dr.CONNECTION_NETWORK_MAC, "00:11:22:33:44:aa")}
    assert device.model is None
    assert device.model_id == "1"
    assert device.sw_version == "WF-RAC-HTTPS, mcu: 200, wireless: 025"


@pytest.mark.usefixtures("mock_repository")
async def test_an_id_that_is_no_mac_claims_no_hardware(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """A different shape would register as somebody else's hardware."""
    airco_id = "not-a-mac"
    entry = _legacy_entry(
        data={**ENTRY_DATA, CONF_AIRCO_ID: airco_id},
        unique_id=airco_id,
        minor_version=2,
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device_by_identifier(
        (DOMAIN, airco_id), entry.entry_id
    )

    assert device is not None
    assert not device.connections


async def test_remove_entry_releases_the_account_slot(
    hass: HomeAssistant,
    mock_repository: MagicMock,
    init_integration: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The module keeps a small table of controllers; removal frees ours."""
    await hass.config_entries.async_remove(init_integration.entry_id)
    await hass.async_block_till_done()

    mock_repository.async_unregister.assert_awaited_once_with(AIRCO_ID)
    assert "Released the controller slot" in caplog.text


async def test_removal_keeps_the_slot_another_entry_still_uses(
    hass: HomeAssistant,
    mock_repository: MagicMock,
    init_integration: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Operator and device ids are shared, so unregistering would free its slot."""
    survivor = _legacy_entry(title="Duplicate", unique_id=None)
    survivor.add_to_hass(hass)
    ir.async_create_issue(
        hass,
        DOMAIN,
        registration_full_issue_id(init_integration.entry_id),
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key="too_many_devices",
        translation_placeholders={"device_name": "Living room"},
    )

    await hass.config_entries.async_remove(init_integration.entry_id)
    await hass.async_block_till_done()

    mock_repository.async_unregister.assert_not_awaited()
    assert not issue_registry.issues


async def test_removal_of_an_entry_that_was_never_migrated(
    hass: HomeAssistant,
    repository_class: MagicMock,
    mock_repository: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """The host may still sit in the options, and the issue goes either way."""
    entry = _legacy_entry(
        data={k: v for k, v in ENTRY_DATA.items() if k != CONF_HOST},
        options={CONF_HOST: HOST},
        version=5,
    )
    entry.add_to_hass(hass)
    ir.async_create_issue(
        hass,
        DOMAIN,
        registration_full_issue_id(entry.entry_id),
        is_fixable=False,
        severity=ir.IssueSeverity.ERROR,
        translation_key="too_many_devices",
        translation_placeholders={"device_name": "Living room"},
    )

    await hass.config_entries.async_remove(entry.entry_id)
    await hass.async_block_till_done()

    assert repository_class.call_args.args[1] == HOST
    mock_repository.async_unregister.assert_awaited_once_with(AIRCO_ID)
    assert not issue_registry.issues


@pytest.mark.parametrize(
    ("side_effect", "answer"),
    [
        pytest.param(WfRacError("no answer"), None, id="no answer"),
        pytest.param(None, False, id="not confirmed"),
    ],
)
async def test_removal_says_so_when_the_slot_is_not_released(
    hass: HomeAssistant,
    mock_repository: MagicMock,
    init_integration: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
    side_effect: Exception | None,
    answer: bool | None,
) -> None:
    """A refused slot release still removes the entry and says so."""
    mock_repository.async_unregister.side_effect = side_effect
    mock_repository.async_unregister.return_value = answer

    await hass.config_entries.async_remove(init_integration.entry_id)
    await hass.async_block_till_done()

    assert "Could not release the controller slot" in caplog.text
    # The log is usually attached to issue reports.
    assert ENTRY_DATA[CONF_OPERATOR_ID] not in caplog.text


async def test_a_failed_platform_unload_keeps_the_coordinator(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_repository: MagicMock,
    init_integration: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Entities that stayed loaded keep the coordinator that feeds them."""
    with patch.object(
        hass.config_entries, "async_unload_platforms", return_value=False
    ):
        assert not await hass.config_entries.async_unload(init_integration.entry_id)
        await hass.async_block_till_done()

    status = mock_repository.async_get_status.return_value
    status.aircon = replace(status.aircon, PresetTemp=25.0)
    await advance_polls(hass, freezer)

    assert hass.states.get(ENTITY_ID).attributes["temperature"] == 25.0


@pytest.mark.usefixtures("mock_repository")
async def test_migration_from_version_1(hass: HomeAssistant) -> None:
    """A v1 entry keeps its host where setup reads it."""
    entry = _legacy_entry(
        data={
            CONF_NAME: "Living room",
            CONF_HOST: HOST,
            CONF_PORT: PORT,
            CONF_DEVICE_ID: ENTRY_DATA[CONF_DEVICE_ID],
            CONF_OPERATOR_ID: ENTRY_DATA[CONF_OPERATOR_ID],
            CONF_AIRCO_ID: AIRCO_ID,
        },
        options={},
        version=1,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert (entry.version, entry.minor_version) == (8, 2)
    assert entry.state is ConfigEntryState.LOADED
    assert entry.data[CONF_HOST] == HOST
    assert CONF_HOST not in entry.options


@pytest.mark.usefixtures("mock_repository")
async def test_migration_brings_the_host_back_into_data(hass: HomeAssistant) -> None:
    """A host kept in options moves back into data, where setup reads it."""
    entry = _legacy_entry(
        data={k: v for k, v in ENTRY_DATA.items() if k != CONF_HOST},
        options={CONF_HOST: HOST},
        version=5,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 8
    assert entry.state is ConfigEntryState.LOADED
    assert entry.data[CONF_HOST] == HOST
    assert CONF_HOST not in entry.options


@pytest.mark.usefixtures("mock_repository")
async def test_migration_drops_the_retired_retry_options(
    hass: HomeAssistant,
) -> None:
    """The retry options no longer exist, so none is left behind."""
    entry = _legacy_entry(
        options={"availability_retry_limit": 5, "availability_retry": 1}, version=3
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 8
    assert not entry.options


@pytest.mark.usefixtures("mock_repository")
async def test_migration_gives_a_hand_added_entry_the_identity_discovery_uses(
    hass: HomeAssistant,
) -> None:
    """A hand-added entry gets the airco id as unique id, so zeroconf recognises it."""
    entry = _legacy_entry(unique_id=None, version=6)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 8
    assert entry.unique_id == AIRCO_ID


@pytest.mark.parametrize(
    ("version", "minor_version"),
    [
        pytest.param(7, 1, id="before_version_8"),
        pytest.param(8, 1, id="version_8_of_the_custom_component"),
    ],
)
@pytest.mark.usefixtures("mock_repository")
async def test_migration_moves_the_entity_unique_id_and_keeps_the_entity_id(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    version: int,
    minor_version: int,
) -> None:
    """The registry entry is renamed in place, so the entity id survives."""
    entry = _legacy_entry(version=version, minor_version=minor_version)
    entry.add_to_hass(hass)
    legacy = entity_registry.async_get_or_create(
        "climate",
        DOMAIN,
        LEGACY_UNIQUE_ID,
        config_entry=entry,
        suggested_object_id="living_room",
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert (entry.version, entry.minor_version) == (8, 2)
    migrated = entity_registry.async_get(legacy.entity_id)
    assert migrated is not None
    assert migrated.unique_id == AIRCO_ID
    assert migrated.entity_id == ENTITY_ID
    assert len(er.async_entries_for_config_entry(entity_registry, entry.entry_id)) == 1


@pytest.mark.usefixtures("mock_repository")
async def test_migration_leaves_foreign_registry_entries_alone(
    hass: HomeAssistant, entity_registry: er.EntityRegistry
) -> None:
    """Only the climate entity's old id is rewritten."""
    entry = _legacy_entry(minor_version=1)
    entry.add_to_hass(hass)
    other = entity_registry.async_get_or_create(
        "sensor", DOMAIN, "something-else", config_entry=entry
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get(other.entity_id).unique_id == "something-else"


@pytest.mark.usefixtures("mock_repository")
async def test_a_current_entry_is_not_migrated(hass: HomeAssistant) -> None:
    """An entry at the current version loads as it is."""
    entry = _legacy_entry(minor_version=2)
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert (entry.version, entry.minor_version) == (8, 2)


@pytest.mark.usefixtures("mock_repository")
async def test_two_legacy_entries_for_one_airco_fail_the_second_migration(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """The second entry for one airco is not migrated and the log names both."""
    first = _legacy_entry(title="Living room", unique_id=None, version=7)
    second = _legacy_entry(title="Old living room", unique_id=None, version=7)
    first.add_to_hass(hass)
    second.add_to_hass(hass)

    await hass.config_entries.async_setup(first.entry_id)
    await hass.async_block_till_done()

    assert first.state is ConfigEntryState.LOADED
    assert first.unique_id == AIRCO_ID
    assert second.state is ConfigEntryState.MIGRATION_ERROR
    assert second.unique_id is None
    assert "Entries Old living room and Living room belong to the same airco" in (
        caplog.text
    )


async def test_removal_clears_the_account_table_issue(
    hass: HomeAssistant,
    mock_repository: MagicMock,
    init_integration: MockConfigEntry,
    issue_registry: ir.IssueRegistry,
) -> None:
    """The issue is entry-scoped and would otherwise point at a dead entry."""
    mock_repository.async_send_command.side_effect = WfRacAccountTableFullError("full")
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            CLIMATE_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: ENTITY_ID}, blocking=True
        )
    assert issue_registry.issues

    await hass.config_entries.async_remove(init_integration.entry_id)
    await hass.async_block_till_done()

    assert not issue_registry.issues
