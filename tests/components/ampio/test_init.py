"""Tests for the Ampio integration setup and teardown."""

import logging
from unittest.mock import MagicMock

from ampio_mqtt import (
    AmpioAuthError,
    AmpioConnectionError,
    AuthFailed,
    AvailabilityChanged,
    ConnectionDied,
)
import pytest

from homeassistant.components.ampio.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration
from .conftest import MSENS_FALLBACK_NAME, MSENS_IDENTIFIER, MSERV_MAC, USER_INPUT, emit

from tests.common import MockConfigEntry


async def test_setup_and_unload(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """The entry loads, and unloading stops the client."""
    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_client.stop.assert_awaited_once()


async def test_shutdown_stops_client(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Home Assistant stopping closes the connection.

    Entries are not unloaded at shutdown, so the stop event is the only place
    the client is reached, and a connection left open there is torn down by
    task cancellation and reported as an outage.
    """
    await setup_integration(hass, mock_config_entry)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    mock_client.stop.assert_awaited_once()


@pytest.mark.parametrize(
    ("start_result", "expected_state"),
    [
        pytest.param(
            AmpioConnectionError("refused"),
            ConfigEntryState.SETUP_RETRY,
            id="connection-error",
        ),
        pytest.param(
            AmpioAuthError("denied"), ConfigEntryState.SETUP_ERROR, id="auth-error"
        ),
        # A discovery cycle that does not complete in time is retryable.
        pytest.param(False, ConfigEntryState.SETUP_RETRY, id="incomplete-discovery"),
    ],
)
async def test_setup_failure_stops_client(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    start_result: Exception | bool,
    expected_state: ConfigEntryState,
) -> None:
    """A failed start maps to the right entry state and stops the client."""
    mock_client.start.side_effect = [start_result]

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is expected_state
    mock_client.stop.assert_awaited_once()


@pytest.mark.usefixtures("mock_client")
async def test_setup_fails_on_server_identity_mismatch(hass: HomeAssistant) -> None:
    """A host now answering as a different M-SERV lands the entry in SETUP_ERROR.

    Proceeding would re-key every unique_id and device identifier under the
    new server's prefix, orphaning the existing registry entries.
    """
    entry = MockConfigEntry(domain=DOMAIN, data=USER_INPUT, unique_id="99999")

    await setup_integration(hass, entry)

    assert entry.state is ConfigEntryState.SETUP_ERROR
    assert entry.error_reason_translation_key == "unexpected_device"


@pytest.mark.usefixtures("mock_client")
async def test_hub_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """The hub device carries the server identity; module devices link to it."""
    await setup_integration(hass, mock_config_entry)

    hub = device_registry.async_get_device_by_identifier(
        (DOMAIN, MSERV_MAC), mock_config_entry.entry_id
    )
    assert hub is not None

    module = device_registry.async_get_device_by_identifier(
        MSENS_IDENTIFIER, mock_config_entry.entry_id
    )
    assert module is not None
    assert module.via_device_id == hub.id


async def test_restricted_account_groups_by_module_mac(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Without the module catalogue, grouping still keys on the leaf-derived mac.

    A standard (non-administrator) account is served the object catalogue but
    no module list, so the module device carries a fallback name and no
    metadata while the entity-to-device mapping matches the admin tier.
    """
    mock_client.modules = {}
    mock_client.mserv = None

    await setup_integration(hass, mock_config_entry)
    assert mock_config_entry.state is ConfigEntryState.LOADED

    hub = device_registry.async_get_device_by_identifier(
        (DOMAIN, MSERV_MAC), mock_config_entry.entry_id
    )
    assert hub is not None
    assert hub.name == "M-SERV"

    module = device_registry.async_get_device_by_identifier(
        MSENS_IDENTIFIER, mock_config_entry.entry_id
    )
    assert module is not None
    assert module.name == MSENS_FALLBACK_NAME
    assert module.model is None
    assert module.via_device_id == hub.id

    entities = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert len(entities) == 8
    assert all(entity.device_id == module.id for entity in entities)


async def test_tier_switch_keeps_device_grouping(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """An entry keeps its devices across account-tier switches in both directions.

    Metadata enriches on an upgrade to admin; a downgrade back to restricted
    degrades the whole device coherently instead of mixing the fallback name
    with stale admin-era metadata.
    """
    admin_modules = mock_client.modules
    admin_mserv = mock_client.mserv
    mock_client.modules = {}
    mock_client.mserv = None

    await setup_integration(hass, mock_config_entry)
    module = device_registry.async_get_device_by_identifier(
        MSENS_IDENTIFIER, mock_config_entry.entry_id
    )
    assert module is not None
    entity_devices = {
        entity.entity_id: entity.device_id
        for entity in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
    }

    mock_client.modules = admin_modules
    mock_client.mserv = admin_mserv
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    enriched = device_registry.async_get_device_by_identifier(
        MSENS_IDENTIFIER, mock_config_entry.entry_id
    )
    assert enriched is not None
    assert enriched.id == module.id
    assert enriched.name == "m-sens salon"
    assert enriched.model == admin_modules[17].model
    assert {
        entity.entity_id: entity.device_id
        for entity in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
    } == entity_devices

    mock_client.modules = {}
    mock_client.mserv = None
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    downgraded = device_registry.async_get_device_by_identifier(
        MSENS_IDENTIFIER, mock_config_entry.entry_id
    )
    assert downgraded is not None
    assert downgraded.id == module.id
    assert downgraded.name == MSENS_FALLBACK_NAME
    assert downgraded.model is None


async def test_runtime_auth_failure_reloads_into_auth_error(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A credential rejection after startup surfaces as an entry auth error.

    The library's reconnect loop stops for good on an unauthorized reconnect;
    the integration schedules a reload, whose setup then raises
    ConfigEntryAuthFailed and lands the entry in SETUP_ERROR.
    """
    await setup_integration(hass, mock_config_entry)
    mock_client.start.side_effect = AmpioAuthError("credentials changed")

    emit(mock_client, AuthFailed(reason="not authorized"))
    await hass.async_block_till_done()

    assert "reloading" in caplog.text
    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    assert mock_config_entry.error_reason_translation_key == "invalid_auth"


async def test_connection_died_reloads_and_recovers(
    hass: HomeAssistant, mock_client: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """A terminal connection-loop crash re-runs setup and recovers."""
    await setup_integration(hass, mock_config_entry)

    emit(mock_client, ConnectionDied(reason="internal error"))
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_client.start.await_count == 2


async def test_availability_transitions_log_once_per_edge(
    hass: HomeAssistant,
    mock_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """One warning on loss, one info on restore, nothing on first connect."""
    await setup_integration(hass, mock_config_entry)

    with caplog.at_level(logging.INFO, logger="homeassistant.components.ampio"):
        emit(mock_client, AvailabilityChanged(available=True))
        emit(mock_client, AvailabilityChanged(available=False))
        emit(mock_client, AvailabilityChanged(available=True))

    assert caplog.text.count("Connection to the Ampio server lost") == 1
    assert caplog.text.count("Connection to the Ampio server restored") == 1
