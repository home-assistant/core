"""Tests for the sensor platform of the Easywave Core integration."""

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

    # pylint: disable-next=home-assistant-tests-registry-fixtures
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

    # pylint: disable-next=home-assistant-tests-registry-fixtures
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
    transceiver = mock_easywave_transceiver()
    await async_setup_easywave_entry(hass, mock_config_entry, transceiver)

    coordinator = mock_config_entry.runtime_data.coordinator
    # pylint: disable-next=home-assistant-tests-registry-fixtures
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{mock_config_entry.entry_id}_rx11_gateway"
    )
    assert entity_id is not None

    events = async_capture_events(hass, EVENT_EASYWAVE)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()
    coordinator._gateway_last_status = "connected"
    disconnect_callback = transceiver.set_disconnect_callback.call_args[0][0]

    disconnect_callback()
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "disconnected"

    events.clear()
    coordinator._gateway_last_status = "disconnected"
    coordinator.is_offline = True
    transceiver.is_connected = True
    connected_callback = transceiver.set_connected_callback.call_args[0][0]
    connected_callback()
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "connected"
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

    # pylint: disable-next=home-assistant-tests-registry-fixtures
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{mock_config_entry.entry_id}_rx11_gateway"
    )
    assert entity_id is not None
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "unknown"

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state is not None

    assert state.state == "connected"


async def test_gateway_sensor_fires_disconnected_event_on_transition(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Gateway disconnected device event is fired when status becomes disconnected."""
    transceiver = mock_easywave_transceiver()
    await async_setup_easywave_entry(hass, mock_config_entry, transceiver)

    coordinator = mock_config_entry.runtime_data.coordinator
    # pylint: disable-next=home-assistant-tests-registry-fixtures
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{mock_config_entry.entry_id}_rx11_gateway"
    )
    assert entity_id is not None

    events = async_capture_events(hass, EVENT_EASYWAVE)
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "connected"

    coordinator._gateway_last_status = "connected"
    disconnect_callback = transceiver.set_disconnect_callback.call_args[0][0]
    disconnect_callback()
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)

    assert state is not None

    assert state.state == "disconnected"
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
    # pylint: disable-next=home-assistant-tests-registry-fixtures
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

    state = hass.states.get(entity_id)

    assert state is not None

    assert state.state == "disconnected"


async def test_gateway_sensor_preserves_offline_device_path_none(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Offline coordinator data keeps an explicit None device_path attribute."""
    transceiver = mock_easywave_transceiver()
    await async_setup_easywave_entry(hass, mock_config_entry, transceiver)

    coordinator = mock_config_entry.runtime_data.coordinator
    # pylint: disable-next=home-assistant-tests-registry-fixtures
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{mock_config_entry.entry_id}_rx11_gateway"
    )
    assert entity_id is not None

    coordinator.async_set_updated_data(
        {"is_connected": True, "device_path": "/dev/ttyACM0"}
    )
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["device_path"] == "/dev/ttyACM0"

    coordinator.async_set_updated_data({"is_connected": False, "device_path": None})
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["device_path"] is None


async def test_gateway_sensor_falls_back_to_configured_path_without_coordinator_path(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Configured path is used only when coordinator data has no device_path key."""
    transceiver = mock_easywave_transceiver()
    await async_setup_easywave_entry(hass, mock_config_entry, transceiver)

    coordinator = mock_config_entry.runtime_data.coordinator
    # pylint: disable-next=home-assistant-tests-registry-fixtures
    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{mock_config_entry.entry_id}_rx11_gateway"
    )
    assert entity_id is not None

    coordinator.async_set_updated_data({"is_connected": True})
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.attributes["device_path"] == mock_config_entry.data["device_path"]
