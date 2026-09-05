"""Test defensive NuHeat integration paths."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

from chemelex_nuheat import HoldUntilStatus, NuHeatApiError, NuHeatAuthError, Thermostat
import pytest

from homeassistant.components.climate import HVACMode
from homeassistant.components.nuheat.account_identity import (
    InvalidAccountSubjectError,
    account_subject_from_entry_data,
)
from homeassistant.components.nuheat.application_credentials import (
    async_get_description_placeholders,
)
from homeassistant.components.nuheat.behavior import api_mode_for_hvac_mode
from homeassistant.components.nuheat.climate import NuHeatClimateEntity
from homeassistant.components.nuheat.const import DOMAIN
from homeassistant.components.nuheat.migration import (
    CONF_MIGRATION_ANCHOR_ENTRY_ID,
    CONF_MIGRATION_SERIAL_NUMBER,
    CONF_MIGRATION_STATE,
    MIGRATION_STATE_PENDING_CLEANUP,
    OAUTH_CONFIG_ENTRY_VERSION,
)
from homeassistant.components.nuheat.registry_migration import (
    DeviceAssociationSnapshot,
    EntityAssociationSnapshot,
    RegistryMigrationError,
    build_registry_snapshots,
    restore_registry_snapshots,
    transfer_registry_ownership,
    validate_registry_snapshots,
    verify_registry_ownership,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_TOKEN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    OAuth2TokenRequestReauthError,
    OAuth2TokenRequestTransientError,
)
from homeassistant.helpers.config_entry_oauth2_flow import (
    ImplementationUnavailableError,
)

from tests.common import MockConfigEntry


def test_account_entry_data_validation() -> None:
    """Test missing and non-string entry access tokens are rejected."""
    for data in (
        {},
        {CONF_TOKEN: None},
        {CONF_TOKEN: {}},
        {CONF_TOKEN: {CONF_ACCESS_TOKEN: 1}},
    ):
        with pytest.raises(InvalidAccountSubjectError):
            account_subject_from_entry_data(data)


async def test_application_credentials_description(hass: HomeAssistant) -> None:
    """Test the development credential documentation link."""
    assert await async_get_description_placeholders(hass) == {
        "docs_url": "https://api.nam.mynuheat.com/"
    }


def test_unsupported_hvac_command() -> None:
    """Test unsupported HVAC commands are rejected."""
    with pytest.raises(ValueError, match="Unsupported HVAC mode"):
        api_mode_for_hvac_mode(HVACMode.COOL)


async def test_setup_implementation_unavailable(hass: HomeAssistant) -> None:
    """Test a temporarily unavailable OAuth implementation retries setup."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_TOKEN: {}}, version=3)
    entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.nuheat.async_get_config_entry_implementation",
            AsyncMock(side_effect=ImplementationUnavailableError),
        ),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
    assert entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    ("error", "expected"),
    [
        (None, None),
        (
            OAuth2TokenRequestReauthError(domain=DOMAIN, request_info=MagicMock()),
            NuHeatAuthError,
        ),
        (
            OAuth2TokenRequestTransientError(domain=DOMAIN, request_info=MagicMock()),
            NuHeatApiError,
        ),
    ],
)
async def test_api_access_token_callback_translation(
    hass: HomeAssistant, error: Exception | None, expected: type[Exception] | None
) -> None:
    """Test forced refresh and OAuth error translation used by the API client."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_TOKEN: {CONF_ACCESS_TOKEN: "synthetic-access"}},
        unique_id="synthetic-subject",
        version=3,
    )
    entry.add_to_hass(hass)
    oauth_session = MagicMock()
    oauth_session.token = {CONF_ACCESS_TOKEN: "synthetic-access"}
    oauth_session.async_ensure_token_valid = AsyncMock(side_effect=[None, error])
    access_token_callback = None

    def make_api(_session, callback):
        nonlocal access_token_callback
        access_token_callback = callback
        return MagicMock()

    async def first_refresh():
        assert access_token_callback is not None
        if expected is None:
            assert await access_token_callback(True) == "synthetic-access"
        else:
            with pytest.raises(expected):
                await access_token_callback(True)

    coordinator = MagicMock()
    coordinator.async_config_entry_first_refresh = first_refresh
    with (
        patch(
            "homeassistant.components.nuheat.async_get_config_entry_implementation",
            AsyncMock(return_value=MagicMock()),
        ),
        patch(
            "homeassistant.components.nuheat.OAuth2Session", return_value=oauth_session
        ),
        patch("homeassistant.components.nuheat.NuHeatClient", side_effect=make_api),
        patch(
            "homeassistant.components.nuheat.NuHeatCoordinator",
            return_value=coordinator,
        ),
        patch.object(hass.config_entries, "async_forward_entry_setups", AsyncMock()),
        patch(
            "homeassistant.components.nuheat.async_resume_migration_cleanup",
            AsyncMock(),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)


async def test_migrate_future_and_pending_entries(hass: HomeAssistant) -> None:
    """Test future entries are rejected and cleanup markers are advanced."""
    future = MockConfigEntry(domain=DOMAIN, data={}, version=99)
    future.add_to_hass(hass)
    assert not await future.async_migrate(hass)

    pending = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_MIGRATION_STATE: MIGRATION_STATE_PENDING_CLEANUP,
            CONF_MIGRATION_ANCHOR_ENTRY_ID: "anchor",
            CONF_MIGRATION_SERIAL_NUMBER: "SERIAL",
        },
        version=1,
    )
    pending.add_to_hass(hass)
    assert await pending.async_migrate(hass)
    assert pending.version == OAUTH_CONFIG_ENTRY_VERSION


def _thermostat(*, current: float | None, target: float | None) -> Thermostat:
    return Thermostat(
        serial_number="SERIAL",
        name="Room",
        current_temperature=current,
        target_temperature=target,
        heating=False,
        online=True,
        mode=3,
        raw_target_temperature=0,
        hold_until=None,
        raw_hold_until=None,
        hold_until_status=HoldUntilStatus.NULL,
    )


def test_entity_missing_temperatures_and_empty_write(hass: HomeAssistant) -> None:
    """Test nullable API temperatures and an empty service call."""
    coordinator = MagicMock()
    coordinator.hass = hass
    coordinator.data = {"SERIAL": _thermostat(current=None, target=None)}
    entity = NuHeatClimateEntity(coordinator, "SERIAL")
    assert entity.current_temperature is None
    assert entity.target_temperature is None


async def test_empty_temperature_write(hass: HomeAssistant) -> None:
    """Test a service call without a temperature is ignored."""
    coordinator = MagicMock()
    coordinator.hass = hass
    coordinator.data = {"SERIAL": _thermostat(current=20, target=21)}
    entity = NuHeatClimateEntity(coordinator, "SERIAL")
    await entity.async_set_temperature()
    coordinator.api.set_target_temperature.assert_not_called()


def _registry_hass(entity_registry: MagicMock, device_registry: MagicMock):
    hass = MagicMock()
    return (
        hass,
        patch(
            "homeassistant.components.nuheat.registry_migration.er.async_get",
            return_value=entity_registry,
        ),
        patch(
            "homeassistant.components.nuheat.registry_migration.dr.async_get",
            return_value=device_registry,
        ),
    )


def test_registry_snapshot_rejects_unrelated_records() -> None:
    """Test registry preflight rejects records owned elsewhere."""
    entity_registry = MagicMock()
    device_registry = MagicMock()
    entity_registry.async_get_entity_id.return_value = "climate.serial"
    entity_registry.async_get.return_value = SimpleNamespace(
        entity_id="climate.serial", config_entry_id="other"
    )
    hass, entity_patch, device_patch = _registry_hass(entity_registry, device_registry)
    with entity_patch, device_patch, pytest.raises(RegistryMigrationError):
        build_registry_snapshots(
            hass, serial_entry_ids=(("SERIAL", "legacy"),), anchor_entry_id="anchor"
        )

    entity_registry.async_get.return_value.config_entry_id = "legacy"
    device_registry.async_get_device.return_value = SimpleNamespace(
        id="device", identifiers=set(), config_entries={"legacy"}
    )
    with entity_patch, device_patch, pytest.raises(RegistryMigrationError):
        build_registry_snapshots(
            hass, serial_entry_ids=(("SERIAL", "legacy"),), anchor_entry_id="anchor"
        )

    device_registry.async_get_device.return_value = SimpleNamespace(
        id="device", identifiers={(DOMAIN, "SERIAL")}, config_entries={"other"}
    )
    with entity_patch, device_patch, pytest.raises(RegistryMigrationError):
        build_registry_snapshots(
            hass, serial_entry_ids=(("SERIAL", "legacy"),), anchor_entry_id="anchor"
        )


@pytest.mark.parametrize(
    "case", ["entity_id", "entity_owner", "device_id", "device_owner"]
)
def test_validate_registry_snapshot_changes(case: str) -> None:
    """Test every registry preflight mutation is detected."""
    entity_registry = MagicMock()
    device_registry = MagicMock()
    entity_registry.async_get_entity_id.return_value = (
        "climate.changed" if case == "entity_id" else "climate.serial"
    )
    entity_registry.async_get.return_value = SimpleNamespace(
        config_entry_id="changed" if case == "entity_owner" else "legacy"
    )
    device_registry.async_get_device.return_value = SimpleNamespace(
        id="changed" if case == "device_id" else "device",
        config_entries={"changed" if case == "device_owner" else "legacy"},
    )
    entity = EntityAssociationSnapshot("SERIAL", "climate.serial", "legacy", "legacy")
    device = DeviceAssociationSnapshot(
        "SERIAL", "device", "legacy", frozenset({"legacy"})
    )
    hass, entity_patch, device_patch = _registry_hass(entity_registry, device_registry)
    with entity_patch, device_patch, pytest.raises(RegistryMigrationError):
        validate_registry_snapshots(hass, (entity,), (device,))


@pytest.mark.parametrize(
    ("case", "entity", "device"),
    [
        ("missing_entity", None, None),
        (
            "changed_entity",
            SimpleNamespace(entity_id="climate.serial", config_entry_id="other"),
            None,
        ),
        (
            "missing_device",
            SimpleNamespace(entity_id="climate.serial", config_entry_id="anchor"),
            None,
        ),
        (
            "device_add_failed",
            SimpleNamespace(entity_id="climate.serial", config_entry_id="anchor"),
            SimpleNamespace(
                id="device", identifiers={(DOMAIN, "SERIAL")}, config_entries={"legacy"}
            ),
        ),
        (
            "device_not_converged",
            SimpleNamespace(entity_id="climate.serial", config_entry_id="anchor"),
            SimpleNamespace(
                id="device",
                identifiers={(DOMAIN, "SERIAL")},
                config_entries={"anchor", "other"},
            ),
        ),
    ],
)
def test_registry_transfer_failures(case: str, entity, device) -> None:
    """Test registry transfer fails closed for inconsistent state."""
    entity_registry = MagicMock()
    device_registry = MagicMock()
    entity_registry.async_get.return_value = entity
    device_registry.async_get.return_value = device
    if case == "device_add_failed":
        device_registry.async_update_device.return_value = None
    entity_snapshot = EntityAssociationSnapshot(
        "SERIAL", "climate.serial", "legacy", "legacy"
    )
    device_snapshot = DeviceAssociationSnapshot(
        "SERIAL", "device", "legacy", frozenset({"legacy"})
    )
    hass, entity_patch, device_patch = _registry_hass(entity_registry, device_registry)
    snapshots = (
        (entity_snapshot,),
        () if case in ("missing_entity", "changed_entity") else (device_snapshot,),
    )
    with entity_patch, device_patch, pytest.raises(RegistryMigrationError):
        transfer_registry_ownership(
            hass,
            anchor_entry_id="anchor",
            entity_snapshots=snapshots[0],
            device_snapshots=snapshots[1],
        )


@pytest.mark.parametrize("case", ["entity", "device"])
def test_verify_registry_ownership_failures(case: str) -> None:
    """Test missing anchor-owned records fail verification."""
    entity_registry = MagicMock()
    device_registry = MagicMock()
    entity_registry.async_get_entity_id.return_value = "climate.serial"
    entity_registry.async_get.return_value = (
        None if case == "entity" else SimpleNamespace(config_entry_id="anchor")
    )
    device_registry.async_get_device.return_value = None
    hass, entity_patch, device_patch = _registry_hass(entity_registry, device_registry)
    with entity_patch, device_patch, pytest.raises(RegistryMigrationError):
        verify_registry_ownership(
            hass, anchor_entry_id="anchor", serial_numbers=frozenset({"SERIAL"})
        )


@pytest.mark.parametrize(
    "case",
    [
        "remove_new",
        "entity_identity",
        "remove_new_device",
        "device_identity",
        "add_failed",
        "remove_failed",
        "not_converged",
    ],
)
def test_restore_registry_snapshot_paths(case: str) -> None:
    """Test rollback cleanup and defensive failures."""
    entity_registry = MagicMock()
    device_registry = MagicMock()
    current_entity_id = "climate.serial"
    entity_snapshot = EntityAssociationSnapshot(
        "SERIAL",
        None if case in ("remove_new", "remove_new_device") else "climate.serial",
        "legacy",
        "legacy",
    )
    if case == "entity_identity":
        current_entity_id = "climate.changed"
    entity_registry.async_get_entity_id.return_value = current_entity_id

    device_snapshot = DeviceAssociationSnapshot(
        "SERIAL",
        None if case in ("remove_new", "remove_new_device") else "device",
        "legacy",
        frozenset({"legacy"}),
    )
    device = SimpleNamespace(id="device", config_entries={"legacy"})
    if case == "device_identity":
        device = None
    elif case in ("add_failed", "not_converged"):
        device.config_entries = {"anchor"}
    elif case == "remove_failed":
        device.config_entries = {"legacy", "anchor"}
    device_registry.async_get_device.return_value = device
    if case in ("add_failed", "remove_failed"):
        device_registry.async_update_device.return_value = None
    elif case == "not_converged":
        device_registry.async_update_device.return_value = SimpleNamespace(
            id="device", config_entries={"legacy", "anchor"}
        )

    hass, entity_patch, device_patch = _registry_hass(entity_registry, device_registry)
    context = (
        pytest.raises(RegistryMigrationError)
        if case not in ("remove_new", "remove_new_device")
        else pytest.raises(Exception, match="never")
    )
    if case in ("remove_new", "remove_new_device"):
        with entity_patch, device_patch:
            restore_registry_snapshots(hass, (entity_snapshot,), (device_snapshot,))
        return
    with entity_patch, device_patch, context:
        restore_registry_snapshots(hass, (entity_snapshot,), (device_snapshot,))
