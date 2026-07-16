"""Tests for user-assisted migration of legacy NuHeat entries."""

from contextlib import ExitStack
from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from chemelex_nuheat import (
    Account,
    NuHeatApiError,
    NuHeatAuthError,
    Thermostat,
    ThermostatMode,
)
import pytest

from homeassistant.components.climate import DOMAIN as CLIMATE_DOMAIN
from homeassistant.components.nuheat.const import CONF_SERIAL_NUMBER, DOMAIN
from homeassistant.components.nuheat.migration import (
    CONF_MIGRATION_STATE,
    CONF_MIGRATION_VALIDATED_SERIALS,
    ISSUE_CLEANUP_INCOMPLETE,
    ISSUE_ROLLBACK_FAILED,
    MIGRATION_STATE_PENDING_CLEANUP,
    OAUTH_CONFIG_ENTRY_VERSION,
    MigrationExecutionError,
    MigrationPreflightError,
    async_consolidate_legacy_entries,
    async_resume_migration_cleanup,
    build_migration_plan,
    execute_migration_plan,
    is_legacy_entry,
    is_legacy_entry_data,
    validate_migration_plan,
)
from homeassistant.components.nuheat.registry_migration import (
    RegistryMigrationError,
    build_registry_snapshots,
    transfer_registry_ownership,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    CONF_ACCESS_TOKEN,
    CONF_PASSWORD,
    CONF_TOKEN,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import (
    area_registry as ar,
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
    label_registry as lr,
)
from homeassistant.helpers.entity_registry import RegistryEntryDisabler

from .helpers import FakeOAuthImplementation, complete_oauth_flow, jwt_access_token

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator

ACCOUNT_SUBJECT = "synthetic-account-subject"
LEGACY_PASSWORD = "synthetic-legacy-password"


def thermostat(serial_number: str, name: str = "Bathroom") -> Thermostat:
    """Return one normalized v2 thermostat."""
    return Thermostat(
        serial_number=serial_number,
        name=name,
        current_temperature=21.0,
        target_temperature=23.0,
        heating=False,
        online=True,
        mode=ThermostatMode.AUTO,
        hold_until=datetime(2026, 7, 8, 1, tzinfo=UTC),
    )


def legacy_data(
    serial_number: str, username: str = "owner@example.com"
) -> dict[str, str]:
    """Return the exact legacy username/password/serial schema."""
    return {
        CONF_USERNAME: username,
        CONF_PASSWORD: LEGACY_PASSWORD,
        CONF_SERIAL_NUMBER: serial_number,
    }


def oauth_data(
    access_token: str | None = None, *, subject: str = ACCOUNT_SUBJECT
) -> dict[str, Any]:
    """Return synthetic Home Assistant OAuth entry data."""
    return {
        "auth_implementation": "test",
        CONF_TOKEN: {
            CONF_ACCESS_TOKEN: access_token or jwt_access_token(subject),
            "refresh_token": "synthetic-refresh-token",
            "expires_at": 4_000_000_000,
            "expires_in": 3600,
        },
    }


def add_legacy_entry(
    hass: HomeAssistant,
    serial_number: str,
    title: str | None = None,
    *,
    username: str = "owner@example.com",
) -> MockConfigEntry:
    """Add a realistic version-1 legacy config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=title or serial_number,
        data=legacy_data(serial_number, username),
        unique_id=serial_number,
        version=1,
    )
    entry.add_to_hass(hass)
    return entry


async def run_migration_flow(
    hass: HomeAssistant,
    hass_client_no_auth: ClientSessionGenerator,
    entry,
    thermostats: list[Thermostat],
    *,
    account: str = "Owner@Example.com",
    subject: str = ACCOUNT_SUBJECT,
):
    """Complete migration through the public reauthentication flow manager."""
    implementation = FakeOAuthImplementation(
        token=oauth_data(subject=subject)[CONF_TOKEN]
    )
    with (
        patch("homeassistant.components.nuheat.config_flow.async_get_clientsession"),
        patch(
            "homeassistant.components.nuheat.config_flow.NuHeatClient.get_account",
            AsyncMock(return_value=Account(account)),
        ),
        patch(
            "homeassistant.components.nuheat.config_flow.NuHeatClient.list_thermostats",
            AsyncMock(return_value=thermostats),
        ),
        patch(
            "homeassistant.components.nuheat.migration._reload_anchor",
            AsyncMock(),
        ),
        patch("homeassistant.components.nuheat.migration.verify_migration_plan_result"),
    ):
        return await complete_oauth_flow(
            hass,
            hass_client_no_auth,
            implementation,
            entry=entry,
            confirmation_step="migration_confirm",
        )


def create_customized_registry_records(
    hass: HomeAssistant, entry: MockConfigEntry, serial_number: str
):
    """Create realistic legacy entity and device records with custom metadata."""
    entity_area = ar.async_get(hass).async_create(f"Entity {serial_number}")
    device_area = ar.async_get(hass).async_create(f"Device {serial_number}")
    label = lr.async_get(hass).async_create(f"Label {serial_number}")

    device_registry = dr.async_get(hass)
    device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, serial_number)},
        manufacturer="NuHeat",
        model="nVent Signature",
        name=f"Legacy {serial_number}",
        serial_number=serial_number,
    )
    device = device_registry.async_update_device(
        device.id,
        area_id=device_area.id,
        name_by_user=f"Custom device {serial_number}",
    )

    entity_registry = er.async_get(hass)
    entity = entity_registry.async_get_or_create(
        CLIMATE_DOMAIN,
        DOMAIN,
        serial_number,
        config_entry=entry,
        device_id=device.id,
        suggested_object_id=f"legacy_{serial_number.lower()}",
    )
    entity = entity_registry.async_update_entity(
        entity.entity_id,
        area_id=entity_area.id,
        disabled_by=RegistryEntryDisabler.USER,
        icon="mdi:radiator",
        labels={label.label_id},
        name=f"Custom entity {serial_number}",
        new_entity_id=(
            "climate.master_bath_floor"
            if serial_number == "ABC123"
            else f"climate.custom_{serial_number.lower()}"
        ),
    )
    return entity, device, entity_area, device_area, label


def build_three_entry_plan(hass: HomeAssistant):
    """Build a migration plan with enough records for first/later failures."""
    entries = [
        add_legacy_entry(hass, "ABC123"),
        add_legacy_entry(hass, "XYZ789"),
        add_legacy_entry(hass, "LMN456"),
    ]
    records = [
        create_customized_registry_records(hass, entry, serial)
        for entry, serial in zip(entries, ("ABC123", "XYZ789", "LMN456"), strict=True)
    ]
    plan = build_migration_plan(
        hass,
        entries[0],
        account_unique_id=ACCOUNT_SUBJECT,
        account_title="Owner@Example.com",
        thermostats=[
            thermostat("ABC123"),
            thermostat("XYZ789"),
            thermostat("LMN456"),
        ],
    )
    return entries, records, plan


def build_existing_anchor_plan(hass: HomeAssistant, *, loaded: bool):
    """Build a migration plan that reuses an existing OAuth account entry."""
    anchor = MockConfigEntry(
        domain=DOMAIN,
        title="Original OAuth account",
        data=oauth_data(subject=ACCOUNT_SUBJECT),
        unique_id=ACCOUNT_SUBJECT,
        version=2,
    )
    anchor.add_to_hass(hass)
    if loaded:
        anchor.mock_state(hass, ConfigEntryState.LOADED)
    legacy = add_legacy_entry(hass, "ABC123", "Original legacy thermostat")
    records = [create_customized_registry_records(hass, legacy, "ABC123")]
    plan = build_migration_plan(
        hass,
        legacy,
        account_unique_id=ACCOUNT_SUBJECT,
        account_title="Renamed OAuth account",
        thermostats=[thermostat("ABC123")],
    )
    return anchor, legacy, records, plan


def local_state(hass: HomeAssistant, entries, records):
    """Capture config and registry fields that migration must preserve."""
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    return {
        "entries": {
            entry.entry_id: (
                dict(entry.data),
                entry.title,
                entry.unique_id,
                entry.version,
            )
            for entry in entries
            if hass.config_entries.async_get_entry(entry.entry_id) is not None
        },
        "entities": {
            entity.id: (
                entity_registry.async_get(entity.entity_id).entity_id,
                entity_registry.async_get(entity.entity_id).config_entry_id,
                entity_registry.async_get(entity.entity_id).name,
                entity_registry.async_get(entity.entity_id).icon,
                entity_registry.async_get(entity.entity_id).area_id,
                entity_registry.async_get(entity.entity_id).disabled_by,
                entity_registry.async_get(entity.entity_id).labels,
                entity_registry.async_get(entity.entity_id).device_id,
            )
            for entity, *_ in records
        },
        "devices": {
            device.id: (
                device_registry.async_get(device.id).config_entries,
                device_registry.async_get(device.id).identifiers,
                device_registry.async_get(device.id).name,
                device_registry.async_get(device.id).name_by_user,
                device_registry.async_get(device.id).area_id,
                device_registry.async_get(device.id).model,
            )
            for _, device, *_ in records
        },
    }


def fail_nth_call(original, occurrence: int):
    """Return a sync wrapper that fails once at the requested call."""
    calls = 0

    def wrapped(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == occurrence:
            raise RuntimeError("synthetic mutation failure")
        return original(*args, **kwargs)

    return wrapped


@pytest.mark.asyncio
async def test_legacy_entry_detection_and_setup_requests_migration(
    hass: HomeAssistant,
) -> None:
    """Legacy credentials are detected without retrying the obsolete API."""
    entry = add_legacy_entry(hass, "ABC123", "Master Bath")
    assert is_legacy_entry_data(entry.data)
    assert is_legacy_entry(entry)
    assert await hass.config_entries.async_setup(entry.entry_id) is False
    await hass.async_block_till_done()
    assert entry.version == 1
    assert entry.data[CONF_PASSWORD] == LEGACY_PASSWORD
    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert entry.error_reason_translation_key == "legacy_migration_required"

    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    result = flows[0]
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "migration_confirm"


@pytest.mark.asyncio
async def test_version_one_oauth_entry_advances_without_legacy_data(
    hass: HomeAssistant,
) -> None:
    """A provisional username ID migrates in place to the token subject."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=oauth_data(),
        unique_id="owner@example.com",
        version=1,
    )
    entry.add_to_hass(hass)
    entry_id = entry.entry_id
    original_data = entry.data
    original_title = entry.title

    with patch(
        "homeassistant.components.nuheat.async_setup_entry",
        AsyncMock(return_value=True),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id) is True
    assert entry.version == OAUTH_CONFIG_ENTRY_VERSION
    assert entry.entry_id == entry_id
    assert entry.unique_id == ACCOUNT_SUBJECT
    assert entry.data is original_data
    assert entry.title == original_title


@pytest.mark.asyncio
async def test_provisional_oauth_subject_migration_preserves_registry_identity(
    hass: HomeAssistant,
) -> None:
    """Changing account identity does not change thermostat-level identity."""
    data = {
        **oauth_data(subject=ACCOUNT_SUBJECT),
        CONF_MIGRATION_STATE: "in_progress",
        CONF_MIGRATION_VALIDATED_SERIALS: ["ABC123"],
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Owner@Example.com",
        data=data,
        unique_id="owner@example.com",
        version=2,
    )
    entry.add_to_hass(hass)
    records = [create_customized_registry_records(hass, entry, "ABC123")]
    before = local_state(hass, [entry], records)
    entry_id = entry.entry_id
    automation_reference = records[0][0].entity_id

    with patch(
        "homeassistant.components.nuheat.async_setup_entry",
        AsyncMock(return_value=True),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id) is True

    assert entry.entry_id == entry_id
    assert entry.unique_id == ACCOUNT_SUBJECT
    assert entry.version == OAUTH_CONFIG_ENTRY_VERSION
    assert entry.title == "Owner@Example.com"
    assert entry.data == data
    after = local_state(hass, [entry], records)
    assert after["entities"] == before["entities"]
    assert after["devices"] == before["devices"]
    entity = er.async_get(hass).async_get(automation_reference)
    assert entity is not None
    assert entity.entity_id == "climate.master_bath_floor"
    assert entity.unique_id == "ABC123"
    assert dr.async_get(hass).async_get(records[0][1].id).id == records[0][1].id


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "access_token", ["malformed", jwt_access_token(None), jwt_access_token("")]
)
async def test_invalid_provisional_subject_fails_without_mutation_or_logging(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    access_token: str,
) -> None:
    """An invalid stored subject leaves provisional entries unchanged."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Owner@Example.com",
        data=oauth_data(access_token),
        unique_id="owner@example.com",
        version=2,
    )
    entry.add_to_hass(hass)
    original = (entry.entry_id, entry.unique_id, entry.version, entry.data, entry.title)

    assert await hass.config_entries.async_setup(entry.entry_id) is False
    assert entry.state is ConfigEntryState.MIGRATION_ERROR
    assert (
        entry.entry_id,
        entry.unique_id,
        entry.version,
        entry.data,
        entry.title,
    ) == (original)
    assert access_token not in caplog.text


@pytest.mark.asyncio
async def test_provisional_subject_migration_rejects_duplicate_without_mutation(
    hass: HomeAssistant,
) -> None:
    """A subject collision is rejected before changing the provisional entry."""
    existing = MockConfigEntry(
        domain=DOMAIN,
        data=oauth_data(subject=ACCOUNT_SUBJECT),
        unique_id=ACCOUNT_SUBJECT,
        version=OAUTH_CONFIG_ENTRY_VERSION,
    )
    existing.add_to_hass(hass)
    provisional = MockConfigEntry(
        domain=DOMAIN,
        title="Owner@Example.com",
        data=oauth_data(subject=ACCOUNT_SUBJECT),
        unique_id="owner@example.com",
        version=2,
    )
    provisional.add_to_hass(hass)

    assert await hass.config_entries.async_setup(provisional.entry_id) is False
    assert provisional.state is ConfigEntryState.MIGRATION_ERROR
    assert provisional.unique_id == "owner@example.com"
    assert provisional.version == 2


@pytest.mark.asyncio
async def test_one_legacy_entry_becomes_oauth_account(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """A validated legacy entry is converted in place and loses its password."""
    entry = add_legacy_entry(hass, "ABC123")
    result = await run_migration_flow(
        hass, hass_client_no_auth, entry, [thermostat("ABC123")]
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "migration_successful"
    assert hass.config_entries.async_get_entry(entry.entry_id) is entry
    assert entry.version == OAUTH_CONFIG_ENTRY_VERSION
    assert entry.unique_id == ACCOUNT_SUBJECT
    assert entry.data[CONF_TOKEN][CONF_ACCESS_TOKEN] == jwt_access_token(
        ACCOUNT_SUBJECT
    )
    assert CONF_USERNAME not in entry.data
    assert CONF_PASSWORD not in entry.data
    assert CONF_SERIAL_NUMBER not in entry.data


@pytest.mark.asyncio
async def test_customized_entity_and_device_survive_initialization(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """Setup reuses legacy registry records and preserves all customization."""
    entry = add_legacy_entry(hass, "ABC123")
    original_entity, original_device, entity_area, device_area, label = (
        create_customized_registry_records(hass, entry, "ABC123")
    )
    result = await run_migration_flow(
        hass, hass_client_no_auth, entry, [thermostat("ABC123")]
    )
    assert result["reason"] == "migration_successful"

    with (
        patch(
            "homeassistant.components.nuheat.async_get_config_entry_implementation",
            AsyncMock(return_value=FakeOAuthImplementation()),
        ),
        patch("homeassistant.components.nuheat.async_get_clientsession", MagicMock()),
        patch(
            "homeassistant.components.nuheat.NuHeatClient.list_thermostats",
            AsyncMock(return_value=[thermostat("ABC123")]),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id) is True
        await hass.async_block_till_done()

    entity_registry = er.async_get(hass)
    entities = [
        item
        for item in entity_registry.entities.values()
        if item.domain == CLIMATE_DOMAIN
        and item.platform == DOMAIN
        and item.unique_id == "ABC123"
    ]
    assert len(entities) == 1
    migrated_entity = entities[0]
    assert migrated_entity.id == original_entity.id
    assert migrated_entity.entity_id == "climate.master_bath_floor"
    assert migrated_entity.name == "Custom entity ABC123"
    assert migrated_entity.icon == "mdi:radiator"
    assert migrated_entity.area_id == entity_area.id
    assert migrated_entity.disabled_by is RegistryEntryDisabler.USER
    assert migrated_entity.labels == {label.label_id}
    assert migrated_entity.config_entry_id == entry.entry_id

    device_registry = dr.async_get(hass)
    devices = [
        item
        for item in device_registry.devices.values()
        if (DOMAIN, "ABC123") in item.identifiers
    ]
    assert len(devices) == 1
    migrated_device = devices[0]
    assert migrated_device.id == original_device.id
    assert migrated_device.area_id == device_area.id
    assert migrated_device.name_by_user == "Custom device ABC123"
    assert migrated_device.model == "nVent Signature"
    assert migrated_device.config_entries == {entry.entry_id}


@pytest.mark.asyncio
async def test_multiple_entries_consolidate_and_transfer_registry_ownership(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """Matching thermostats share one account entry without registry churn."""
    anchor = add_legacy_entry(hass, "ABC123")
    redundant = add_legacy_entry(hass, "XYZ789")
    entity_a, device_a, *_ = create_customized_registry_records(hass, anchor, "ABC123")
    entity_b, device_b, *_ = create_customized_registry_records(
        hass, redundant, "XYZ789"
    )

    result = await run_migration_flow(
        hass,
        hass_client_no_auth,
        anchor,
        [thermostat("ABC123"), thermostat("XYZ789", "Kitchen")],
    )

    assert result["reason"] == "migration_successful"
    assert hass.config_entries.async_get_entry(redundant.entry_id) is None
    assert hass.config_entries.async_entries(DOMAIN) == [anchor]
    entity_registry = er.async_get(hass)
    assert entity_registry.async_get(entity_a.entity_id).id == entity_a.id
    migrated_b = entity_registry.async_get(entity_b.entity_id)
    assert migrated_b.id == entity_b.id
    assert migrated_b.config_entry_id == anchor.entry_id
    assert (
        len(
            [
                item
                for item in entity_registry.entities.values()
                if item.platform == DOMAIN and item.unique_id in {"ABC123", "XYZ789"}
            ]
        )
        == 2
    )

    device_registry = dr.async_get(hass)
    assert device_registry.async_get(device_a.id).id == device_a.id
    migrated_device_b = device_registry.async_get(device_b.id)
    assert migrated_device_b.id == device_b.id
    assert migrated_device_b.config_entries == {anchor.entry_id}
    assert (
        len(
            [
                item
                for item in device_registry.devices.values()
                if item.identifiers & {(DOMAIN, "ABC123"), (DOMAIN, "XYZ789")}
            ]
        )
        == 2
    )


@pytest.mark.asyncio
async def test_unrelated_and_temporarily_omitted_entries_remain_untouched(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """Only serials returned by this account are eligible for consolidation."""
    anchor = add_legacy_entry(hass, "ABC123")
    omitted = add_legacy_entry(hass, "XYZ789")
    unrelated = add_legacy_entry(hass, "OTHER1", username="other@example.com")
    omitted_data = dict(omitted.data)
    unrelated_data = dict(unrelated.data)

    result = await run_migration_flow(
        hass, hass_client_no_auth, anchor, [thermostat("ABC123")]
    )

    assert result["reason"] == "migration_successful"
    assert hass.config_entries.async_get_entry(omitted.entry_id) is omitted
    assert hass.config_entries.async_get_entry(unrelated.entry_id) is unrelated
    assert omitted.data == omitted_data
    assert unrelated.data == unrelated_data
    assert omitted.data[CONF_PASSWORD] == LEGACY_PASSWORD
    assert unrelated.data[CONF_PASSWORD] == LEGACY_PASSWORD


@pytest.mark.asyncio
async def test_wrong_account_rolls_back_without_registry_changes(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """The initiating serial must exist before any local mutation occurs."""
    entry = add_legacy_entry(hass, "ABC123")
    entity, device, *_ = create_customized_registry_records(hass, entry, "ABC123")
    original_data = dict(entry.data)

    result = await run_migration_flow(
        hass, hass_client_no_auth, entry, [thermostat("DIFFERENT")]
    )

    assert result["reason"] == "migration_account_mismatch"
    assert entry.version == 1
    assert entry.unique_id == "ABC123"
    assert entry.data == original_data
    assert (
        er.async_get(hass).async_get(entity.entity_id).config_entry_id == entry.entry_id
    )
    assert dr.async_get(hass).async_get(device.id).config_entries == {entry.entry_id}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "reason"),
    [
        (NuHeatAuthError("synthetic OAuth rejection"), "invalid_auth"),
        (NuHeatApiError("synthetic API failure"), "cannot_connect"),
    ],
)
async def test_oauth_and_api_failures_leave_legacy_state_unchanged(
    hass: HomeAssistant,
    error: Exception,
    reason: str,
    caplog: pytest.LogCaptureFixture,
    hass_client_no_auth: ClientSessionGenerator,
) -> None:
    """Remote failures occur before any destructive migration operation."""
    entry = add_legacy_entry(hass, "ABC123")
    entity, device, *_ = create_customized_registry_records(hass, entry, "ABC123")
    original_data = dict(entry.data)
    authorization_code = jwt_access_token(
        ACCOUNT_SUBJECT, marker="synthetic-authorization-code-not-for-logs"
    )
    implementation = FakeOAuthImplementation(
        token=oauth_data(authorization_code)[CONF_TOKEN]
    )

    with (
        patch("homeassistant.components.nuheat.config_flow.async_get_clientsession"),
        patch(
            "homeassistant.components.nuheat.config_flow.NuHeatClient.get_account",
            AsyncMock(side_effect=error),
        ),
    ):
        result = await complete_oauth_flow(
            hass,
            hass_client_no_auth,
            implementation,
            entry=entry,
            confirmation_step="migration_confirm",
        )

    assert result["reason"] == reason
    assert entry.data == original_data
    assert entry.version == 1
    assert hass.config_entries.async_get_entry(entry.entry_id) is entry
    assert (
        er.async_get(hass).async_get(entity.entity_id).config_entry_id == entry.entry_id
    )
    assert dr.async_get(hass).async_get(device.id).config_entries == {entry.entry_id}
    assert LEGACY_PASSWORD not in caplog.text
    assert authorization_code not in caplog.text
    assert "synthetic-refresh-token" not in caplog.text


@pytest.mark.asyncio
async def test_existing_oauth_account_absorbs_matching_legacy_entry(
    hass: HomeAssistant, hass_client_no_auth: ClientSessionGenerator
) -> None:
    """Migration reuses an existing account entry rather than duplicating it."""
    account_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Owner@Example.com",
        data=oauth_data(subject=ACCOUNT_SUBJECT),
        unique_id="owner@example.com",
        version=2,
    )
    account_entry.add_to_hass(hass)
    account_entry_id = account_entry.entry_id
    legacy = add_legacy_entry(hass, "ABC123")
    entity, device, *_ = create_customized_registry_records(hass, legacy, "ABC123")

    result = await run_migration_flow(
        hass, hass_client_no_auth, legacy, [thermostat("ABC123")]
    )

    assert result["reason"] == "migration_successful"
    assert hass.config_entries.async_get_entry(legacy.entry_id) is None
    assert hass.config_entries.async_entries(DOMAIN) == [account_entry]
    assert account_entry.entry_id == account_entry_id
    assert account_entry.unique_id == ACCOUNT_SUBJECT
    assert account_entry.version == OAUTH_CONFIG_ENTRY_VERSION
    assert account_entry.data[CONF_TOKEN][CONF_ACCESS_TOKEN] == jwt_access_token(
        ACCOUNT_SUBJECT
    )
    assert er.async_get(hass).async_get(entity.entity_id).config_entry_id == (
        account_entry.entry_id
    )
    assert dr.async_get(hass).async_get(device.id).config_entries == {
        account_entry.entry_id
    }


@pytest.mark.asyncio
async def test_direct_consolidation_reports_only_confirmed_serials(
    hass: HomeAssistant,
) -> None:
    """The migration result documents exactly which entries were validated."""
    anchor = add_legacy_entry(hass, "ABC123")
    unmatched = add_legacy_entry(hass, "XYZ789")

    with (
        patch(
            "homeassistant.components.nuheat.migration._reload_anchor",
            AsyncMock(),
        ),
        patch("homeassistant.components.nuheat.migration.verify_migration_plan_result"),
    ):
        result = await async_consolidate_legacy_entries(
            hass,
            anchor,
            oauth_data=oauth_data(),
            account_unique_id=ACCOUNT_SUBJECT,
            account_title="Owner@Example.com",
            thermostats=[thermostat("ABC123")],
        )

    assert result.anchor_entry is anchor
    assert result.migrated_serials == {"ABC123"}
    assert result.removed_entry_ids == ()
    assert hass.config_entries.async_get_entry(unmatched.entry_id) is unmatched


def test_registry_transfer_rejects_an_unexpected_owner(
    hass: HomeAssistant,
) -> None:
    """A conflicting registry owner aborts instead of recreating the entity."""
    old_entry = add_legacy_entry(hass, "ABC123")
    anchor_entry = MockConfigEntry(
        domain=DOMAIN,
        data=oauth_data(),
        unique_id=ACCOUNT_SUBJECT,
        version=OAUTH_CONFIG_ENTRY_VERSION,
    )
    anchor_entry.add_to_hass(hass)
    unrelated_entry = MockConfigEntry(
        domain=DOMAIN,
        data=oauth_data("unrelated-token"),
        unique_id="unrelated@example.com",
        version=OAUTH_CONFIG_ENTRY_VERSION,
    )
    unrelated_entry.add_to_hass(hass)
    entity = er.async_get(hass).async_get_or_create(
        CLIMATE_DOMAIN,
        DOMAIN,
        "ABC123",
        config_entry=unrelated_entry,
        suggested_object_id="conflicting_floor",
    )

    with pytest.raises(RegistryMigrationError):
        build_registry_snapshots(
            hass,
            serial_entry_ids=(("ABC123", old_entry.entry_id),),
            anchor_entry_id=anchor_entry.entry_id,
        )

    assert er.async_get(hass).async_get(entity.entity_id).config_entry_id == (
        unrelated_entry.entry_id
    )


def test_migration_plan_is_immutable_and_revalidates_before_execution(
    hass: HomeAssistant,
) -> None:
    """The detached preflight plan rejects later local-state changes."""
    entries, records, plan = build_three_entry_plan(hass)
    before = local_state(hass, entries, records)

    with pytest.raises(FrozenInstanceError):
        plan.anchor_entry_id = "replacement"  # type: ignore[misc]
    with pytest.raises(TypeError):
        plan.original_anchor_data[CONF_PASSWORD] = "changed"  # type: ignore[index]

    restarted_plan = build_migration_plan(
        hass,
        entries[0],
        account_unique_id=ACCOUNT_SUBJECT,
        account_title="Owner@Example.com",
        thermostats=[thermostat(serial) for serial in plan.validated_serials],
    )
    assert restarted_plan.anchor_entry_id == plan.anchor_entry_id
    assert restarted_plan.redundant_entry_ids == plan.redundant_entry_ids
    assert restarted_plan.entity_snapshots == plan.entity_snapshots
    assert restarted_plan.device_snapshots == plan.device_snapshots

    duplicate = MockConfigEntry(
        domain=DOMAIN,
        data=oauth_data("duplicate-token"),
        unique_id=plan.account_unique_id,
        version=OAUTH_CONFIG_ENTRY_VERSION,
    )
    duplicate.add_to_hass(hass)
    with pytest.raises(MigrationPreflightError):
        validate_migration_plan(hass, plan)

    assert local_state(hass, entries, records) == before


@pytest.mark.asyncio
async def test_rollback_restores_loaded_existing_oauth_anchor(
    hass: HomeAssistant,
) -> None:
    """A failed migration returns a previously loaded OAuth anchor to service."""
    anchor, legacy, records, plan = build_existing_anchor_plan(hass, loaded=True)
    before = local_state(hass, [anchor, legacy], records)

    async def unload_anchor(entry_id: str) -> bool:
        assert entry_id == anchor.entry_id
        anchor.mock_state(hass, ConfigEntryState.NOT_LOADED)
        return True

    async def setup_anchor(entry_id: str) -> bool:
        assert entry_id == anchor.entry_id
        anchor.mock_state(hass, ConfigEntryState.LOADED)
        return True

    with (
        patch(
            "homeassistant.components.nuheat.migration._reload_anchor",
            AsyncMock(side_effect=RuntimeError("synthetic reload failure")),
        ),
        patch.object(
            hass.config_entries,
            "async_unload",
            AsyncMock(side_effect=unload_anchor),
        ) as unload,
        patch.object(
            hass.config_entries,
            "async_setup",
            AsyncMock(side_effect=setup_anchor),
        ) as setup,
        pytest.raises(MigrationExecutionError),
    ):
        await execute_migration_plan(hass, plan, oauth_data=oauth_data())

    assert plan.anchor_was_loaded is True
    assert local_state(hass, [anchor, legacy], records) == before
    assert anchor.state is ConfigEntryState.LOADED
    unload.assert_awaited_once_with(anchor.entry_id)
    setup.assert_awaited_once_with(anchor.entry_id)
    assert (
        ir.async_get(hass).async_get_issue(
            DOMAIN, f"{ISSUE_ROLLBACK_FAILED}_{anchor.entry_id}"
        )
        is None
    )


@pytest.mark.asyncio
async def test_rollback_leaves_originally_unloaded_anchor_unloaded(
    hass: HomeAssistant,
) -> None:
    """Rollback does not load an OAuth anchor that was originally offline."""
    anchor, legacy, records, plan = build_existing_anchor_plan(hass, loaded=False)
    before = local_state(hass, [anchor, legacy], records)

    with (
        patch(
            "homeassistant.components.nuheat.migration._reload_anchor",
            AsyncMock(side_effect=RuntimeError("synthetic reload failure")),
        ),
        patch.object(hass.config_entries, "async_setup", AsyncMock()) as setup,
        pytest.raises(MigrationExecutionError),
    ):
        await execute_migration_plan(hass, plan, oauth_data=oauth_data())

    assert plan.anchor_was_loaded is False
    assert local_state(hass, [anchor, legacy], records) == before
    assert anchor.state is ConfigEntryState.NOT_LOADED
    setup.assert_not_awaited()
    assert (
        ir.async_get(hass).async_get_issue(
            DOMAIN, f"{ISSUE_ROLLBACK_FAILED}_{anchor.entry_id}"
        )
        is None
    )


@pytest.mark.asyncio
async def test_rollback_loaded_state_restore_failure_creates_repair_issue(
    hass: HomeAssistant,
) -> None:
    """Failure to restart a previously loaded anchor makes rollback incomplete."""
    anchor, _, _, plan = build_existing_anchor_plan(hass, loaded=True)

    async def unload_anchor(entry_id: str) -> bool:
        anchor.mock_state(hass, ConfigEntryState.NOT_LOADED)
        return True

    with (
        patch(
            "homeassistant.components.nuheat.migration._reload_anchor",
            AsyncMock(side_effect=RuntimeError("synthetic reload failure")),
        ),
        patch.object(
            hass.config_entries,
            "async_unload",
            AsyncMock(side_effect=unload_anchor),
        ),
        patch.object(
            hass.config_entries, "async_setup", AsyncMock(return_value=False)
        ) as setup,
        pytest.raises(MigrationExecutionError),
    ):
        await execute_migration_plan(hass, plan, oauth_data=oauth_data())

    setup.assert_awaited_once_with(anchor.entry_id)
    assert anchor.state is ConfigEntryState.NOT_LOADED
    assert (
        ir.async_get(hass).async_get_issue(
            DOMAIN, f"{ISSUE_ROLLBACK_FAILED}_{anchor.entry_id}"
        )
        is not None
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("failure_point", "occurrence"),
    [
        ("entity", 1),
        ("entity", 2),
        ("device", 1),
        ("device", 2),
        ("anchor_update", 1),
        ("reload", 1),
        ("verification", 1),
        ("first_cleanup", 1),
    ],
)
async def test_pre_boundary_failures_restore_exact_local_state(
    hass: HomeAssistant,
    caplog: pytest.LogCaptureFixture,
    failure_point: str,
    occurrence: int,
) -> None:
    """Every failure before the first removal restores original local state."""
    entries, records, plan = build_three_entry_plan(hass)
    unrelated = add_legacy_entry(hass, "OTHER1", username="unrelated@example.invalid")
    before = local_state(hass, [*entries, unrelated], records)
    entity_registry = er.async_get(hass)
    device_registry = dr.async_get(hass)
    original_remove = hass.config_entries.async_remove

    async def fail_first_remove(entry_id):
        raise RuntimeError("synthetic cleanup failure")

    with ExitStack() as stack:
        stack.enter_context(
            patch(
                "homeassistant.components.nuheat.migration._reload_anchor", AsyncMock()
            )
        )
        stack.enter_context(
            patch(
                "homeassistant.components.nuheat.migration.verify_migration_plan_result"
            )
        )
        if failure_point == "entity":
            stack.enter_context(
                patch.object(
                    entity_registry,
                    "async_update_entity",
                    side_effect=fail_nth_call(
                        entity_registry.async_update_entity, occurrence
                    ),
                )
            )
        elif failure_point == "device":
            stack.enter_context(
                patch.object(
                    device_registry,
                    "async_update_device",
                    side_effect=fail_nth_call(
                        device_registry.async_update_device, occurrence
                    ),
                )
            )
        elif failure_point == "anchor_update":
            stack.enter_context(
                patch.object(
                    hass.config_entries,
                    "async_update_entry",
                    side_effect=fail_nth_call(
                        hass.config_entries.async_update_entry, occurrence
                    ),
                )
            )
        elif failure_point == "reload":
            stack.enter_context(
                patch(
                    "homeassistant.components.nuheat.migration._reload_anchor",
                    AsyncMock(side_effect=RuntimeError("synthetic reload failure")),
                )
            )
        elif failure_point == "verification":
            stack.enter_context(
                patch(
                    "homeassistant.components.nuheat.migration.verify_migration_plan_result",
                    side_effect=RuntimeError("synthetic verification failure"),
                )
            )
        elif failure_point == "first_cleanup":
            stack.enter_context(
                patch.object(
                    hass.config_entries,
                    "async_remove",
                    side_effect=fail_first_remove,
                )
            )

        with pytest.raises(MigrationExecutionError):
            await execute_migration_plan(hass, plan, oauth_data=oauth_data())

    assert hass.config_entries.async_remove == original_remove
    assert local_state(hass, [*entries, unrelated], records) == before
    assert len(er.async_get(hass).entities) == 3
    assert len(dr.async_get(hass).devices) == 3
    assert LEGACY_PASSWORD not in caplog.text
    assert "synthetic-access-token" not in caplog.text
    assert "synthetic-refresh-token" not in caplog.text
    issue_reg = ir.async_get(hass)
    assert (
        issue_reg.async_get_issue(
            DOMAIN, f"{ISSUE_ROLLBACK_FAILED}_{plan.anchor_entry_id}"
        )
        is None
    )


@pytest.mark.asyncio
async def test_later_cleanup_failure_is_resumable_after_restart(
    hass: HomeAssistant,
) -> None:
    """Cleanup after the removal boundary leaves a usable, retryable anchor."""
    entries, records, plan = build_three_entry_plan(hass)
    unrelated = add_legacy_entry(hass, "OTHER1", username="unrelated@example.invalid")
    unrelated_data = dict(unrelated.data)
    original_remove = hass.config_entries.async_remove
    remove_calls = 0

    async def fail_second_remove(entry_id):
        nonlocal remove_calls
        remove_calls += 1
        if remove_calls == 2:
            raise RuntimeError("synthetic later cleanup failure")
        return await original_remove(entry_id)

    with (
        patch("homeassistant.components.nuheat.migration._reload_anchor", AsyncMock()),
        patch("homeassistant.components.nuheat.migration.verify_migration_plan_result"),
        patch.object(
            hass.config_entries, "async_remove", side_effect=fail_second_remove
        ),
    ):
        result = await execute_migration_plan(hass, plan, oauth_data=oauth_data())

    assert result.cleanup_complete is False
    assert len(result.removed_entry_ids) == 1
    assert len(result.pending_cleanup_entry_ids) == 1
    assert CONF_PASSWORD not in entries[0].data
    assert entries[0].data[CONF_MIGRATION_STATE]
    pending = hass.config_entries.async_get_entry(result.pending_cleanup_entry_ids[0])
    assert pending is not None
    assert pending.data[CONF_MIGRATION_STATE] == MIGRATION_STATE_PENDING_CLEANUP
    assert hass.config_entries.async_get_entry(unrelated.entry_id) is unrelated
    assert unrelated.data == unrelated_data
    assert (
        ir.async_get(hass).async_get_issue(
            DOMAIN, f"{ISSUE_CLEANUP_INCOMPLETE}_{plan.anchor_entry_id}"
        )
        is not None
    )

    entries[0].runtime_data = SimpleNamespace(
        coordinator=SimpleNamespace(
            data={serial: thermostat(serial) for serial in plan.validated_serials}
        )
    )
    await async_resume_migration_cleanup(hass, entries[0])

    assert hass.config_entries.async_get_entry(pending.entry_id) is None
    assert CONF_MIGRATION_STATE not in entries[0].data
    assert CONF_MIGRATION_VALIDATED_SERIALS not in entries[0].data
    assert CONF_PASSWORD not in entries[0].data
    assert hass.config_entries.async_get_entry(unrelated.entry_id) is unrelated
    assert (
        ir.async_get(hass).async_get_issue(
            DOMAIN, f"{ISSUE_CLEANUP_INCOMPLETE}_{plan.anchor_entry_id}"
        )
        is None
    )
    for entity, device, *_ in records:
        assert er.async_get(hass).async_get(entity.entity_id).id == entity.id
        assert er.async_get(hass).async_get(entity.entity_id).config_entry_id == (
            entries[0].entry_id
        )
        assert dr.async_get(hass).async_get(device.id).config_entries == {
            entries[0].entry_id
        }


@pytest.mark.asyncio
async def test_rollback_failure_creates_secret_free_repair_issue(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Incomplete restoration is visible without logging credential values."""
    entries, _, plan = build_three_entry_plan(hass)
    entity_registry = er.async_get(hass)

    with (
        patch.object(
            entity_registry,
            "async_update_entity",
            side_effect=RuntimeError("synthetic registry failure"),
        ),
        patch("homeassistant.components.nuheat.migration._reload_anchor", AsyncMock()),
        patch("homeassistant.components.nuheat.migration.verify_migration_plan_result"),
        pytest.raises(MigrationExecutionError),
    ):
        await execute_migration_plan(hass, plan, oauth_data=oauth_data())

    assert (
        ir.async_get(hass).async_get_issue(
            DOMAIN, f"{ISSUE_ROLLBACK_FAILED}_{entries[0].entry_id}"
        )
        is not None
    )
    assert "restoration from backup may be required" in caplog.text
    for secret in (
        LEGACY_PASSWORD,
        "synthetic-access-token",
        "synthetic-refresh-token",
        "synthetic-authorization-code",
    ):
        assert secret not in caplog.text


@pytest.mark.asyncio
async def test_restart_after_registry_transfer_converges_without_duplicates(
    hass: HomeAssistant,
) -> None:
    """A process stop after ownership transfer is safe to plan and retry."""
    entries, records, plan = build_three_entry_plan(hass)
    transfer_registry_ownership(
        hass,
        anchor_entry_id=plan.anchor_entry_id,
        entity_snapshots=plan.entity_snapshots,
        device_snapshots=plan.device_snapshots,
    )

    retry_plan = build_migration_plan(
        hass,
        entries[0],
        account_unique_id=ACCOUNT_SUBJECT,
        account_title="Owner@Example.com",
        thermostats=[thermostat(serial) for serial in plan.validated_serials],
    )
    with (
        patch("homeassistant.components.nuheat.migration._reload_anchor", AsyncMock()),
        patch("homeassistant.components.nuheat.migration.verify_migration_plan_result"),
    ):
        result = await execute_migration_plan(hass, retry_plan, oauth_data=oauth_data())

    assert result.cleanup_complete is True
    assert hass.config_entries.async_entries(DOMAIN) == [entries[0]]
    assert CONF_PASSWORD not in entries[0].data
    assert len(er.async_get(hass).entities) == len(records)
    assert len(dr.async_get(hass).devices) == len(records)


@pytest.mark.asyncio
async def test_restart_after_anchor_conversion_resumes_cleanup(
    hass: HomeAssistant,
) -> None:
    """A process stop after durable markers converges during next setup."""
    entries, records, plan = build_three_entry_plan(hass)
    with (
        patch(
            "homeassistant.components.nuheat.migration._reload_anchor",
            AsyncMock(side_effect=KeyboardInterrupt),
        ),
        pytest.raises(KeyboardInterrupt),
    ):
        await execute_migration_plan(hass, plan, oauth_data=oauth_data())

    assert entries[0].data[CONF_MIGRATION_STATE]
    assert entries[0].data[CONF_PASSWORD] == LEGACY_PASSWORD
    assert all(
        entry.data[CONF_MIGRATION_STATE] == MIGRATION_STATE_PENDING_CLEANUP
        for entry in entries[1:]
    )
    entries[0].runtime_data = SimpleNamespace(
        coordinator=SimpleNamespace(
            data={serial: thermostat(serial) for serial in plan.validated_serials}
        )
    )

    await async_resume_migration_cleanup(hass, entries[0])

    assert hass.config_entries.async_entries(DOMAIN) == [entries[0]]
    assert CONF_PASSWORD not in entries[0].data
    assert CONF_MIGRATION_STATE not in entries[0].data
    assert len(er.async_get(hass).entities) == len(records)
    assert len(dr.async_get(hass).devices) == len(records)


@pytest.mark.asyncio
async def test_retry_after_successful_rollback_completes(
    hass: HomeAssistant,
) -> None:
    """A rolled-back migration can be planned again and completed."""
    entries, records, plan = build_three_entry_plan(hass)
    with (
        patch(
            "homeassistant.components.nuheat.migration._reload_anchor",
            AsyncMock(side_effect=RuntimeError("synthetic first-attempt failure")),
        ),
        patch("homeassistant.components.nuheat.migration.verify_migration_plan_result"),
        pytest.raises(MigrationExecutionError),
    ):
        await execute_migration_plan(hass, plan, oauth_data=oauth_data())

    retry_plan = build_migration_plan(
        hass,
        entries[0],
        account_unique_id=ACCOUNT_SUBJECT,
        account_title="Owner@Example.com",
        thermostats=[thermostat(serial) for serial in plan.validated_serials],
    )
    with (
        patch("homeassistant.components.nuheat.migration._reload_anchor", AsyncMock()),
        patch("homeassistant.components.nuheat.migration.verify_migration_plan_result"),
    ):
        result = await execute_migration_plan(hass, retry_plan, oauth_data=oauth_data())

    assert result.cleanup_complete is True
    assert hass.config_entries.async_entries(DOMAIN) == [entries[0]]
    assert CONF_PASSWORD not in entries[0].data
    assert len(er.async_get(hass).entities) == len(records)
    assert len(dr.async_get(hass).devices) == len(records)
