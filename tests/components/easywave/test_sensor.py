"""Tests for the sensor platform of the Easywave Core integration."""

from unittest.mock import AsyncMock

from homeassistant.components.easywave.const import DOMAIN, EVENT_EASYWAVE
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers import entity_registry as er

from .conftest import async_setup_easywave_entry, mock_easywave_transceiver

from tests.common import MockConfigEntry, async_capture_events


async def test_sensor_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that sensor platform setup creates a gateway sensor entity."""
    await async_setup_easywave_entry(hass, mock_config_entry)

    registry = er.async_get(hass)
    entity_id = registry.async_get_entity_id(
        "sensor", DOMAIN, f"{mock_config_entry.entry_id}_rx11_gateway"
    )
    assert entity_id is not None

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes.get("friendly_name") is not None

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def test_gateway_sensor_reports_connected_after_coordinator_update(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Gateway connection status is exposed via entity state after coordinator refresh."""
    transceiver = mock_easywave_transceiver()
    await async_setup_easywave_entry(hass, mock_config_entry, transceiver)

    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{mock_config_entry.entry_id}_rx11_gateway"
    )
    assert entity_id is not None

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await mock_config_entry.runtime_data.coordinator.async_refresh()
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "connected"
    assert state.attributes["icon"] == "mdi:usb"

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def test_gateway_sensor_fires_connected_event_on_transition(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Gateway connected device event is fired when status becomes connected."""
    transceiver = mock_easywave_transceiver(connected=False)
    transceiver.reconnect = transceiver.connect
    await async_setup_easywave_entry(hass, mock_config_entry, transceiver)

    coordinator = mock_config_entry.runtime_data.coordinator
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{mock_config_entry.entry_id}_rx11_gateway"
    )
    assert entity_id is not None

    events = async_capture_events(hass, EVENT_EASYWAVE)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "disconnected"

    transceiver.is_connected = True
    transceiver.reconnect = transceiver.connect = AsyncMock(return_value=True)
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "connected"
    assert len(events) == 1
    assert events[0].data["type"] == "gateway_connected"

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def test_gateway_sensor_waits_for_homeassistant_started(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Gateway sensor defers its first write until Home Assistant has started."""
    object.__setattr__(hass, "state", CoreState.not_running)
    await async_setup_easywave_entry(hass, mock_config_entry)

    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{mock_config_entry.entry_id}_rx11_gateway"
    )
    assert entity_id is not None
    assert hass.states.get(entity_id).state == "unknown"

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "connected"


async def test_gateway_sensor_fires_disconnected_event_on_transition(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Gateway disconnected device event is fired when status becomes disconnected."""
    transceiver = mock_easywave_transceiver()
    await async_setup_easywave_entry(hass, mock_config_entry, transceiver)

    coordinator = mock_config_entry.runtime_data.coordinator
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{mock_config_entry.entry_id}_rx11_gateway"
    )
    assert entity_id is not None

    events = async_capture_events(hass, EVENT_EASYWAVE)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == "connected"

    transceiver.is_connected = False
    coordinator.is_offline = False
    coordinator.async_set_updated_data(
        {"is_connected": False, "device_path": "/dev/ttyACM0"}
    )
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "disconnected"
    assert any(event.data["type"] == "gateway_disconnected" for event in events)

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()


async def test_gateway_sensor_reports_disconnected_when_link_is_down(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Gateway status is disconnected when the transceiver link is down but not offline."""
    transceiver = mock_easywave_transceiver()
    await async_setup_easywave_entry(hass, mock_config_entry, transceiver)

    coordinator = mock_config_entry.runtime_data.coordinator
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{mock_config_entry.entry_id}_rx11_gateway"
    )
    assert entity_id is not None

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await coordinator.async_refresh()
    await hass.async_block_till_done()

    transceiver.is_connected = False
    coordinator.is_offline = False
    coordinator.async_set_updated_data(
        {"is_connected": False, "device_path": "/dev/ttyACM0"}
    )
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "disconnected"
