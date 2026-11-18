"""Test Hikvision integration setup and unload."""

import logging
from unittest.mock import MagicMock
import uuid
from xml.etree.ElementTree import ParseError

import pytest
from pytest_homeassistant.common import MockConfigEntry
import requests

from homeassistant.components.hikvision.const import CONF_RANDOM_ID, DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import (
    CONF_PASSWORD,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    EVENT_HOMEASSISTANT_STOP,
    STATE_UNAVAILABLE,
)
from homeassistant.core import DOMAIN as HOMEASSISTANT_DOMAIN, CoreState, HomeAssistant
from homeassistant.helpers import (
    device_registry as dr,
    entity_registry as er,
    issue_registry as ir,
)

from . import setup_integration
from .conftest import TEST_DEVICE_ID, TEST_HOST, TEST_PASSWORD, TEST_PORT, TEST_USERNAME


async def test_setup_and_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test successful setup and unload of config entry."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_hikcamera.return_value.start_stream.assert_called_once()

    # Verify HikCamera was called with the verify_ssl parameter
    mock_hikcamera.assert_called_once_with(
        f"http://{TEST_HOST}", TEST_PORT, TEST_USERNAME, TEST_PASSWORD, True
    )

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED
    mock_hikcamera.return_value.disconnect.assert_called_once()


async def test_stream_stopped_on_shutdown(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test the event stream thread is joined before the event loop closes."""
    await setup_integration(hass, mock_config_entry)

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    mock_hikcamera.return_value.disconnect.assert_called_once()


async def test_stream_stopped_when_shutdown_starts_during_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test the stream is stopped when shutdown begins while setting up."""
    hass.set_state(CoreState.stopping)

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    mock_hikcamera.return_value.disconnect.assert_called_once()


async def test_setup_entry_with_ssl(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test setup with ssl enabled passes ssl parameter to HikCamera."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, data={**mock_config_entry.data, CONF_SSL: True}
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    # Verify HikCamera was called over HTTPS, verifying the certificate
    mock_hikcamera.assert_called_once_with(
        f"https://{TEST_HOST}", TEST_PORT, TEST_USERNAME, TEST_PASSWORD, True
    )


@pytest.mark.parametrize(
    ("entry_data", "expected_verify_ssl"),
    [
        ({CONF_VERIFY_SSL: False}, False),
        ({CONF_VERIFY_SSL: True}, True),
        # Entries created before the option existed keep verifying
        (None, True),
    ],
    ids=["unverified", "verified", "legacy_entry"],
)
async def test_setup_entry_ssl_verification(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    entry_data: dict[str, bool] | None,
    expected_verify_ssl: bool,
) -> None:
    """Test the certificate verification choice is passed to HikCamera."""
    data = {**mock_config_entry.data, CONF_SSL: True}
    data.pop(CONF_VERIFY_SSL)
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry, data={**data, **(entry_data or {})}
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_hikcamera.assert_called_once_with(
        f"https://{TEST_HOST}",
        TEST_PORT,
        TEST_USERNAME,
        TEST_PASSWORD,
        expected_verify_ssl,
    )


async def test_setup_entry_connection_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test setup fails on connection error."""
    mock_hikcamera.side_effect = requests.exceptions.RequestException(
        "Connection failed"
    )

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_no_device_id(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test setup fails when device_id is None."""
    mock_hikcamera.return_value.get_id = None

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize("amount_of_channels", [2])
@pytest.mark.parametrize("verify_ssl", [True, False])
async def test_setup_entry_nvr_channels_ssl_verification(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hik_nvr: MagicMock,
    mock_hik_get_channels: MagicMock,
    verify_ssl: bool,
) -> None:
    """Test the certificate verification choice is used to list NVR channels."""
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        data={**mock_config_entry.data, CONF_SSL: True, CONF_VERIFY_SSL: verify_ssl},
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_hik_get_channels.assert_called_once_with(
        TEST_HOST, TEST_PORT, TEST_USERNAME, TEST_PASSWORD, True, verify_ssl
    )


async def test_setup_entry_nvr_fetches_events(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hik_nvr: MagicMock,
) -> None:
    """Test setup fetches NVR events for NVR devices."""
    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_hik_nvr.return_value.get_event_triggers.assert_called_once()
    mock_hik_nvr.return_value.inject_events.assert_called_once()


async def test_setup_entry_nvr_skips_videoloss(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hik_nvr: MagicMock,
) -> None:
    """Test NVR event injection skips videoloss (watchdog event)."""
    mock_hik_nvr.return_value.get_event_triggers.return_value = {
        "VMD": [1, 2],
        "videoloss": [1, 2, 3],
    }

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_hik_nvr.return_value.inject_events.assert_called_once_with({"Motion": [1, 2]})


async def test_setup_entry_nvr_skips_unmapped_events(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hik_nvr: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test NVR event injection skips events not in SENSOR_MAP."""
    mock_hik_nvr.return_value.get_event_triggers.return_value = {
        "VMD": [1],
        "audioexception": [1, 2],
    }

    with caplog.at_level(logging.DEBUG):
        await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_hik_nvr.return_value.inject_events.assert_called_once_with({"Motion": [1]})
    assert "Skipping unmapped event type: audioexception" in caplog.text


async def test_setup_entry_nvr_skips_all_unknown_events(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hik_nvr: MagicMock,
) -> None:
    """Test NVR event injection with only unknown events does not inject."""
    mock_hik_nvr.return_value.get_event_triggers.return_value = {
        "videoloss": [1],
        "audioexception": [2],
    }

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_hik_nvr.return_value.inject_events.assert_not_called()


async def test_setup_entry_nvr_event_fetch_request_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hik_nvr: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup continues when NVR event fetch fails with request error."""
    mock_hik_nvr.return_value.get_event_triggers.side_effect = (
        requests.exceptions.RequestException("Connection error")
    )

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_hik_nvr.return_value.get_event_triggers.assert_called_once()
    mock_hik_nvr.return_value.inject_events.assert_not_called()
    assert f"Unable to fetch event triggers from {TEST_HOST}" in caplog.text


async def test_setup_entry_nvr_event_fetch_parse_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hik_nvr: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup continues when NVR event fetch fails with parse error."""
    mock_hik_nvr.return_value.get_event_triggers.side_effect = ParseError("Invalid XML")

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_hik_nvr.return_value.get_event_triggers.assert_called_once()
    mock_hik_nvr.return_value.inject_events.assert_not_called()
    assert f"Unable to fetch event triggers from {TEST_HOST}" in caplog.text


async def test_setup_entry_nvr_no_events_returned(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hik_nvr: MagicMock,
) -> None:
    """Test setup continues when NVR returns no events."""
    mock_hik_nvr.return_value.get_event_triggers.return_value = None

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_hik_nvr.return_value.get_event_triggers.assert_called_once()
    mock_hik_nvr.return_value.inject_events.assert_not_called()


async def test_setup_entry_nvr_empty_events_returned(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hik_nvr: MagicMock,
) -> None:
    """Test setup continues when NVR returns empty events."""
    mock_hik_nvr.return_value.get_event_triggers.return_value = {}

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.LOADED
    mock_hik_nvr.return_value.get_event_triggers.assert_called_once()
    mock_hik_nvr.return_value.inject_events.assert_not_called()


async def test_setup_with_rejected_credentials_starts_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test a rejected password asks for new credentials instead of retrying."""
    mock_hikcamera.return_value.get_id = None
    mock_hikcamera.return_value.auth_failed = True

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id
    # Core also raises a repair for the entry, linking to the reauth flow.
    assert issue_registry.async_get_issue(
        HOMEASSISTANT_DOMAIN,
        f"config_entry_reauth_{DOMAIN}_{mock_config_entry.entry_id}",
    )


async def test_setup_unreachable_device_is_retried(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
) -> None:
    """Test a device that gives no ID, without rejecting the login, is retried."""
    mock_hikcamera.return_value.get_id = None

    await setup_integration(hass, mock_config_entry)

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert not hass.config_entries.flow.async_progress()


def _identities(
    hass: HomeAssistant, entry: MockConfigEntry
) -> tuple[set[str], set[tuple[str, str]]]:
    """Return the unique IDs of an entry's entities, and its devices' identifiers."""
    entities = {
        entity.unique_id
        for entity in er.async_entries_for_config_entry(
            er.async_get(hass), entry.entry_id
        )
    }
    devices = {
        identifier
        for device in dr.async_entries_for_config_entry(
            dr.async_get(hass), entry.entry_id
        )
        for identifier in device.identifiers
    }
    return entities, devices


async def test_a_device_with_a_made_up_id_keeps_its_entities(
    hass: HomeAssistant,
    mock_hikcamera: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a device whose ID pyHik makes up keeps its device and entities.

    pyHik makes up a new UUID at every connection for a device whose own ID is too
    short. The entities are registered under the entry's own ID instead, while the
    events of the stream are still matched with the ID pyHik gives now.
    """
    stored = str(uuid.uuid4())
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, unique_id=stored)
    camera = mock_hikcamera.return_value
    first = uuid.uuid4()
    camera.get_id = first
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entities, devices = _identities(hass, mock_config_entry)
    assert entities
    assert all(unique_id.startswith(stored) for unique_id in entities)
    assert (DOMAIN, stored) in devices
    callbacks = {call.args[1] for call in camera.add_update_callback.call_args_list}
    assert callbacks
    assert all(callback.startswith(f"{first}.") for callback in callbacks)

    # A reauthentication reloads the entry, and pyHik makes up another ID.
    result = await mock_config_entry.start_reauth_flow(hass)
    second = uuid.uuid4()
    camera.get_id = second
    camera.add_update_callback.reset_mock()
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: TEST_USERNAME, CONF_PASSWORD: "new-password"},
    )
    await hass.async_block_till_done()
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert _identities(hass, mock_config_entry) == (entities, devices)
    callbacks = {call.args[1] for call in camera.add_update_callback.call_args_list}
    assert callbacks
    assert all(callback.startswith(f"{second}.") for callback in callbacks)


@pytest.mark.parametrize(
    "stored",
    [TEST_DEVICE_ID, str(uuid.uuid5(uuid.NAMESPACE_URL, "serialNumber:sn1"))],
    ids=["real_id", "derived_id"],
)
async def test_an_entry_with_a_real_id_does_not_lend_it_to_a_made_up_one(
    hass: HomeAssistant,
    mock_hikcamera: MagicMock,
    mock_config_entry: MockConfigEntry,
    stored: str,
) -> None:
    """Test a camera with a made-up ID does not take over a real device's identity.

    A replacement camera at the same address, whose own ID is too short, would
    otherwise be registered under the original device and its entities.
    """
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, unique_id=stored)
    made_up = uuid.uuid4()
    mock_hikcamera.return_value.get_id = made_up

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entities, devices = _identities(hass, mock_config_entry)
    assert entities
    assert all(unique_id.startswith(str(made_up)) for unique_id in entities)
    assert devices == {(DOMAIN, str(made_up))}


async def test_entities_of_an_earlier_made_up_id_are_kept_on_upgrade(
    hass: HomeAssistant,
    mock_hikcamera: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the entities registered before the entry kept its ID are not replaced.

    Before, the user flow and each setup got different random IDs from pyHik, so
    the entities are registered under another ID than the entry's own. They move to
    it, with their entity IDs: automations that use them keep working.
    """
    earlier = str(uuid.uuid4())
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, unique_id=earlier)
    camera = mock_hikcamera.return_value
    camera.get_id = uuid.UUID(earlier)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    entities, devices = _identities(hass, mock_config_entry)
    assert entities
    assert devices == {(DOMAIN, earlier)}
    entity_ids = {
        entry.entity_id
        for entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
    }
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # The entry was created with another ID than the one its entities have.
    own = str(uuid.uuid4())
    hass.config_entries.async_update_entry(mock_config_entry, unique_id=own)
    camera.get_id = uuid.uuid4()
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    registered = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    assert {entry.entity_id for entry in registered} == entity_ids
    assert {entry.unique_id for entry in registered} == {
        own + unique_id.removeprefix(earlier) for unique_id in entities
    }
    assert _identities(hass, mock_config_entry)[1] == {(DOMAIN, own)}
    enabled = [entry.entity_id for entry in registered if not entry.disabled_by]
    assert enabled
    assert all(
        hass.states.get(entity_id).state != STATE_UNAVAILABLE for entity_id in enabled
    )


async def test_the_oldest_entity_of_earlier_made_up_ids_is_kept(
    hass: HomeAssistant,
    mock_hikcamera: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test of several earlier random IDs, the oldest entity moves to the entry's.

    Each setup registered a new one, with a suffixed entity ID; the first one has
    the entity ID automations use. The others are left as they are.
    """
    first, later, own = (str(uuid.uuid4()) for _ in range(3))
    mock_config_entry.add_to_hass(hass)
    oldest = entity_registry.async_get_or_create(
        "binary_sensor",
        DOMAIN,
        f"{first}_Motion_1",
        config_entry=mock_config_entry,
        suggested_object_id="front_camera_motion",
    )
    newer = entity_registry.async_get_or_create(
        "binary_sensor",
        DOMAIN,
        f"{later}_Motion_1",
        config_entry=mock_config_entry,
        suggested_object_id="front_camera_motion",
    )
    assert newer.entity_id != oldest.entity_id
    oldest_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id, identifiers={(DOMAIN, first)}
    )
    newer_device = device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id, identifiers={(DOMAIN, later)}
    )
    # An entity of the camera's real ID, from a firmware that reported one, is not
    # an earlier made-up one.
    real = entity_registry.async_get_or_create(
        "binary_sensor",
        DOMAIN,
        f"{TEST_DEVICE_ID}_Tamper Detection_1",
        config_entry=mock_config_entry,
    )
    hass.config_entries.async_update_entry(mock_config_entry, unique_id=own)
    mock_hikcamera.return_value.get_id = uuid.uuid4()

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get(oldest.entity_id).unique_id == f"{own}_Motion_1"
    assert entity_registry.async_get(newer.entity_id).unique_id == f"{later}_Motion_1"
    assert entity_registry.async_get(real.entity_id).unique_id == (
        f"{TEST_DEVICE_ID}_Tamper Detection_1"
    )
    assert device_registry.async_get(oldest_device.id).identifiers == {(DOMAIN, own)}
    assert device_registry.async_get(newer_device.id).identifiers == {(DOMAIN, later)}


async def test_an_entry_with_a_real_id_adopts_no_made_up_entities(
    hass: HomeAssistant,
    mock_hikcamera: MagicMock,
    mock_config_entry: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test entities under a made-up ID are only moved to an entry's made-up ID."""
    made_up = str(uuid.uuid4())
    mock_config_entry.add_to_hass(hass)
    legacy = entity_registry.async_get_or_create(
        "binary_sensor", DOMAIN, f"{made_up}_Motion_1", config_entry=mock_config_entry
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        entity_registry.async_get(legacy.entity_id).unique_id == f"{made_up}_Motion_1"
    )


@pytest.mark.parametrize(
    ("answer", "recorded"),
    [
        # The device gives the entry's ID as its own.
        ("stored", False),
        # pyHik makes up a random ID, as it did when the entry was created.
        ("made_up", True),
        # Another device, or another ID: nothing is settled.
        ("other", None),
    ],
)
async def test_where_an_older_entrys_id_came_from_is_recorded(
    hass: HomeAssistant,
    mock_hikcamera: MagicMock,
    mock_config_entry: MockConfigEntry,
    answer: str,
    recorded: bool | None,
) -> None:
    """Test an entry created before the origin of its ID was recorded gets it.

    Its ID has the form of a random one pyHik makes up, which a device's own ID
    can have too.
    """
    stored = str(uuid.uuid4())
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(mock_config_entry, unique_id=stored)
    assert CONF_RANDOM_ID not in mock_config_entry.data
    mock_hikcamera.return_value.get_id = {
        "stored": stored,
        "made_up": uuid.uuid4(),
        "other": "DS-OTHER0000000000000",
    }[answer]

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.data.get(CONF_RANDOM_ID) is recorded


async def test_a_devices_own_random_uuid_is_not_lent_to_a_made_up_one(
    hass: HomeAssistant,
    mock_hikcamera: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an entry whose own ID is a random UUID keeps it for its own device only."""
    own = str(uuid.uuid4())
    mock_config_entry.add_to_hass(hass)
    hass.config_entries.async_update_entry(
        mock_config_entry,
        unique_id=own,
        data={**mock_config_entry.data, CONF_RANDOM_ID: False},
    )
    made_up = uuid.uuid4()
    mock_hikcamera.return_value.get_id = made_up

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entities, devices = _identities(hass, mock_config_entry)
    assert entities
    assert all(unique_id.startswith(str(made_up)) for unique_id in entities)
    assert devices == {(DOMAIN, str(made_up))}


async def test_a_device_with_its_own_id_uses_it(
    hass: HomeAssistant,
    mock_hikcamera: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a real device ID is what the entities and the events both use."""
    await setup_integration(hass, mock_config_entry)

    entities, devices = _identities(hass, mock_config_entry)
    device_id = mock_hikcamera.return_value.get_id
    assert all(unique_id.startswith(device_id) for unique_id in entities)
    assert (DOMAIN, device_id) in devices
    callbacks = {
        call.args[1]
        for call in mock_hikcamera.return_value.add_update_callback.call_args_list
    }
    assert all(callback.startswith(f"{device_id}.") for callback in callbacks)
