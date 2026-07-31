"""Tests for the Nobø Ecohub integration setup."""

import logging
from unittest.mock import MagicMock

from pynobo import nobo as pynobo_nobo
import pytest

from homeassistant.components.nobo_hub.const import (
    CONF_OVERRIDE_TYPE,
    CONF_SERIAL,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_IP_ADDRESS, CONF_MAC, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import (
    device_identifiers,
    dispatch_hub_update,
    entity_unique_ids,
    fire_hub_connection,
    fire_hub_update,
)
from .conftest import SERIAL, STORED_IP

from tests.common import MockConfigEntry

NEW_IP = "192.168.1.55"
GLOBAL_ENTITY = "select.my_eco_hub_global_override"


@pytest.fixture
def platforms(request: pytest.FixtureRequest) -> list[Platform]:
    """Default to select; override per-test via indirect parametrize."""
    return getattr(request, "param", [Platform.SELECT])


async def test_setup_uses_stored_ip(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nobo_class: MagicMock,
) -> None:
    """Setup connects using the stored IP without invoking rediscovery."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_nobo_class.call_args.kwargs["ip"] == STORED_IP
    assert mock_nobo_class.call_args.kwargs["discover"] is False
    mock_nobo_class.async_discover_hubs.assert_not_called()


async def test_setup_rediscovery_updates_ip(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nobo_class: MagicMock,
) -> None:
    """A failed direct connect falls back to rediscovery and persists the new IP."""
    mock_config_entry.add_to_hass(hass)
    failing_hub = MagicMock(spec=pynobo_nobo)
    failing_hub.connect.side_effect = OSError("Unreachable")
    mock_nobo_class.side_effect = [failing_hub, mock_nobo_class.return_value]
    mock_nobo_class.async_discover_hubs.return_value = {(NEW_IP, SERIAL)}

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED
    assert mock_config_entry.data[CONF_IP_ADDRESS] == NEW_IP
    assert mock_nobo_class.call_count == 2
    assert mock_nobo_class.call_args_list[0].kwargs["ip"] == STORED_IP
    assert mock_nobo_class.call_args_list[1].kwargs["ip"] == NEW_IP


async def test_setup_retries_when_rediscovery_finds_nothing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nobo_class: MagicMock,
) -> None:
    """Setup retries when stored IP fails and rediscovery is empty."""
    mock_config_entry.add_to_hass(hass)
    failing_hub = MagicMock(spec=pynobo_nobo)
    failing_hub.connect.side_effect = OSError("Unreachable")
    mock_nobo_class.side_effect = [failing_hub]
    mock_nobo_class.async_discover_hubs.return_value = set()

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry.error_reason_translation_key == "cannot_connect"
    assert mock_config_entry.error_reason_translation_placeholders == {
        "serial": SERIAL,
        "ip": STORED_IP,
    }


async def test_setup_retries_when_rediscovered_ip_also_fails(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nobo_class: MagicMock,
) -> None:
    """Setup retries when both stored and rediscovered IPs fail."""
    mock_config_entry.add_to_hass(hass)
    first_failing_hub = MagicMock(spec=pynobo_nobo)
    first_failing_hub.connect.side_effect = OSError("Unreachable")
    second_failing_hub = MagicMock(spec=pynobo_nobo)
    second_failing_hub.connect.side_effect = OSError("Unreachable")
    mock_nobo_class.side_effect = [first_failing_hub, second_failing_hub]
    mock_nobo_class.async_discover_hubs.return_value = {(NEW_IP, SERIAL)}

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY
    assert mock_config_entry.error_reason_translation_key == "cannot_connect"
    assert mock_config_entry.error_reason_translation_placeholders == {
        "serial": SERIAL,
        "ip": NEW_IP,
    }


@pytest.mark.parametrize(
    ("stored_options", "expected_options"),
    [
        ({CONF_OVERRIDE_TYPE: "Constant"}, {CONF_OVERRIDE_TYPE: "constant"}),
        ({CONF_OVERRIDE_TYPE: "Now"}, {CONF_OVERRIDE_TYPE: "now"}),
        ({CONF_OVERRIDE_TYPE: "constant"}, {CONF_OVERRIDE_TYPE: "constant"}),
        ({}, {}),
    ],
    ids=["Constant", "Now", "already_lowercase", "no_options"],
)
async def test_migrate_options(
    hass: HomeAssistant,
    mock_nobo_class: MagicMock,
    stored_options: dict[str, str],
    expected_options: dict[str, str],
) -> None:
    """Migrating from minor_version 1 lowercases override_type and bumps version."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="My Eco Hub",
        unique_id=SERIAL,
        data={
            CONF_SERIAL: SERIAL,
            CONF_IP_ADDRESS: STORED_IP,
        },
        options=stored_options,
        version=1,
        minor_version=1,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.minor_version == 3
    assert entry.options == expected_options


async def test_migrate_data_drops_auto_discovered(
    hass: HomeAssistant,
    mock_nobo_class: MagicMock,
) -> None:
    """The auto_discovered key is stripped from entry.data on migration."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="My Eco Hub",
        unique_id=SERIAL,
        data={
            CONF_SERIAL: SERIAL,
            CONF_IP_ADDRESS: STORED_IP,
            "auto_discovered": True,
        },
        version=1,
        minor_version=2,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.minor_version == 3
    assert entry.data == {
        CONF_SERIAL: SERIAL,
        CONF_IP_ADDRESS: STORED_IP,
    }
    assert entry.options == {}


async def test_setup_registers_hub_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
    mock_nobo_class: MagicMock,
) -> None:
    """The hub device is registered with the expected metadata."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device(identifiers={(DOMAIN, SERIAL)})
    assert device is not None
    assert device.config_entries == {mock_config_entry.entry_id}
    assert device.name == "My Eco Hub"
    assert device.manufacturer == "Glen Dimplex Nordic AS"
    assert device.model == "Nobø Ecohub"
    assert device.serial_number == SERIAL
    assert device.sw_version == "115"
    assert device.hw_version == "hw"
    assert device.connections == set()


async def test_setup_registers_hub_device_with_mac(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    mock_nobo_class: MagicMock,
) -> None:
    """An entry with a stored MAC surfaces it via DeviceInfo.connections."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="My Eco Hub",
        unique_id=SERIAL,
        data={
            CONF_SERIAL: SERIAL,
            CONF_IP_ADDRESS: STORED_IP,
            CONF_MAC: "7C8306011192",
        },
        version=1,
        minor_version=3,
    )
    entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    device = device_registry.async_get_device(identifiers={(DOMAIN, SERIAL)})
    assert device is not None
    assert device.connections == {
        (dr.CONNECTION_NETWORK_MAC, "7c:83:06:01:11:92"),
    }


@pytest.mark.usefixtures("init_integration")
async def test_entity_available_when_hub_connected(hass: HomeAssistant) -> None:
    """Entities are available when the hub reports connected."""
    state = hass.states.get(GLOBAL_ENTITY)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE


@pytest.mark.usefixtures("init_integration")
async def test_entity_unavailable_on_disconnect_and_recovers(
    hass: HomeAssistant,
    mock_nobo_hub: MagicMock,
) -> None:
    """Entities become unavailable on disconnect and recover on reconnect."""
    assert hass.states.get(GLOBAL_ENTITY).state != STATE_UNAVAILABLE

    await fire_hub_connection(hass, mock_nobo_hub, False)
    assert hass.states.get(GLOBAL_ENTITY).state == STATE_UNAVAILABLE

    await fire_hub_connection(hass, mock_nobo_hub, True)
    assert hass.states.get(GLOBAL_ENTITY).state != STATE_UNAVAILABLE


@pytest.mark.usefixtures("init_integration")
async def test_log_on_disconnect_and_reconnect(
    hass: HomeAssistant,
    mock_nobo_hub: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Disconnects and reconnects both log at info level."""
    caplog.clear()
    await fire_hub_connection(hass, mock_nobo_hub, False)
    assert any(
        record.levelno == logging.INFO
        and "Lost connection to Nobø Ecohub" in record.message
        for record in caplog.records
    )

    caplog.clear()
    await fire_hub_connection(hass, mock_nobo_hub, True)
    assert any(
        record.levelno == logging.INFO
        and "Reconnected to Nobø Ecohub" in record.message
        for record in caplog.records
    )


@pytest.mark.usefixtures("init_integration")
async def test_connection_callbacks_deregistered_on_unload(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_nobo_hub: MagicMock,
) -> None:
    """Every registered connection callback is deregistered on entry unload."""
    registered = mock_nobo_hub.register_connection_callback.call_count
    assert registered > 0

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_nobo_hub.deregister_connection_callback.call_count == registered


@pytest.mark.parametrize("platforms", [[Platform.CLIMATE]], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_zone_removed_during_disconnect_stays_unavailable_on_reconnect(
    hass: HomeAssistant,
    mock_nobo_hub: MagicMock,
) -> None:
    """A zone removed via the Nobø app while disconnected stays unavailable on reconnect.

    The connection callback fires before the data callback (pynobo Option C).
    Without the `available` property's existence check, the connection callback's
    `_attr_available = True` would briefly flip the entity to available before the
    data callback's _read_state could re-mark it unavailable.
    """
    entity = "climate.living_room_living_room"
    assert hass.states.get(entity).state != STATE_UNAVAILABLE

    await fire_hub_connection(hass, mock_nobo_hub, False)
    assert hass.states.get(entity).state == STATE_UNAVAILABLE

    # Simulate the zone being removed via the Nobø app while disconnected:
    # by the time the hub reconnects and _get_initial_data runs, hub.zones
    # no longer contains the zone.
    mock_nobo_hub.zones = {}

    await fire_hub_connection(hass, mock_nobo_hub, True)
    assert hass.states.get(entity).state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("init_integration")
async def test_removed_zone_removes_device(
    hass: HomeAssistant,
    mock_nobo_hub: MagicMock,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Removing a zone on the hub removes its device but keeps the hub device."""
    entry_id = mock_config_entry.entry_id
    assert (DOMAIN, f"{SERIAL}:1") in device_identifiers(device_registry, entry_id)

    del mock_nobo_hub.zones["1"]
    await fire_hub_update(hass, mock_nobo_hub)

    identifiers = device_identifiers(device_registry, entry_id)
    assert (DOMAIN, f"{SERIAL}:1") not in identifiers
    assert (DOMAIN, SERIAL) in identifiers


@pytest.mark.parametrize("platforms", [[Platform.SENSOR]], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_removed_component_removes_device(
    hass: HomeAssistant,
    mock_nobo_hub: MagicMock,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Removing a temperature-sensor component on the hub removes its device."""
    entry_id = mock_config_entry.entry_id
    assert (DOMAIN, "200000059091") in device_identifiers(device_registry, entry_id)

    del mock_nobo_hub.components["200000059091"]
    await fire_hub_update(hass, mock_nobo_hub)

    assert (DOMAIN, "200000059091") not in device_identifiers(device_registry, entry_id)


@pytest.mark.usefixtures("init_integration")
async def test_disconnected_hub_does_not_remove_devices(
    hass: HomeAssistant,
    mock_nobo_hub: MagicMock,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Devices are retained when topology looks empty because the hub is disconnected."""
    entry_id = mock_config_entry.entry_id
    before = device_identifiers(device_registry, entry_id)

    mock_nobo_hub.connected = False
    mock_nobo_hub.zones.clear()
    mock_nobo_hub.components.clear()
    await fire_hub_update(hass, mock_nobo_hub)

    assert device_identifiers(device_registry, entry_id) == before


@pytest.mark.parametrize(
    "platforms",
    [[Platform.CLIMATE, Platform.SELECT, Platform.SENSOR]],
    indirect=True,
)
@pytest.mark.usefixtures("init_integration")
async def test_disconnect_does_not_readd_entities_on_reconnect(
    hass: HomeAssistant,
    mock_nobo_hub: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A stale empty topology while disconnected must not forget known ids.

    Otherwise the reconcile would clear the known-id sets and re-add every
    entity on reconnect, colliding with the still-registered unique ids.
    """
    saved_zones = dict(mock_nobo_hub.zones)
    saved_components = dict(mock_nobo_hub.components)

    mock_nobo_hub.connected = False
    mock_nobo_hub.zones.clear()
    mock_nobo_hub.components.clear()
    await fire_hub_update(hass, mock_nobo_hub)

    mock_nobo_hub.connected = True
    mock_nobo_hub.zones.update(saved_zones)
    mock_nobo_hub.components.update(saved_components)
    await fire_hub_update(hass, mock_nobo_hub)

    assert "already exists" not in caplog.text


@pytest.mark.parametrize("platforms", [[Platform.CLIMATE]], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_buffered_remove_then_readd_same_id(
    hass: HomeAssistant,
    mock_nobo_hub: MagicMock,
    entity_registry: er.EntityRegistry,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """A buffered remove + same-id re-add (no event-loop yield between) re-registers cleanly.

    pynobo can process a delete and an id-reusing add back-to-back before the
    loop yields (buffered messages), so synchronous device removal must fully
    deregister the old entity before the re-add, or the add collides with the
    still-registered unique id.
    """
    entry_id = mock_config_entry.entry_id
    zone = {
        "zone_id": "2",
        "name": "Bedroom",
        "week_profile_id": "0",
        "temp_comfort_c": "22",
        "temp_eco_c": "18",
    }
    mock_nobo_hub.zones["2"] = zone
    await fire_hub_update(hass, mock_nobo_hub)
    assert f"{SERIAL}:2" in entity_unique_ids(entity_registry, entry_id)

    # Remove then re-add the same id with no await (no event-loop yield) between.
    del mock_nobo_hub.zones["2"]
    dispatch_hub_update(mock_nobo_hub)
    mock_nobo_hub.zones["2"] = zone
    dispatch_hub_update(mock_nobo_hub)
    await hass.async_block_till_done()

    assert f"{SERIAL}:2" in entity_unique_ids(entity_registry, entry_id)
    assert "already exists" not in caplog.text


@pytest.mark.usefixtures("mock_nobo_class")
async def test_stale_device_pruned_at_setup(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """A device for a zone removed while Home Assistant was down is pruned at setup."""
    mock_config_entry.add_to_hass(hass)
    stale_device = (DOMAIN, f"{SERIAL}:99")
    device_registry.async_get_or_create(
        config_entry_id=mock_config_entry.entry_id,
        identifiers={stale_device},
    )
    entry_id = mock_config_entry.entry_id
    assert stale_device in device_identifiers(device_registry, entry_id)

    assert await hass.config_entries.async_setup(entry_id)
    await hass.async_block_till_done()

    assert stale_device not in device_identifiers(device_registry, entry_id)
