"""Tests for the sensor platform of the Easywave Core integration."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.easywave.const import DOMAIN, EVENT_EASYWAVE
from homeassistant.const import EVENT_HOMEASSISTANT_STARTED
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry, async_capture_events


def _patch_integration() -> tuple[Any, Any, MagicMock]:
    """Return patches and a fully stubbed coordinator for sensor platform tests."""
    mock_transceiver = MagicMock()
    mock_transceiver.is_connected = True
    mock_transceiver.usb_serial_number = "12345"
    mock_transceiver.hw_version = "1.0"
    mock_transceiver.fw_version = "2.0"
    mock_transceiver.device_path = "/dev/ttyACM0"

    mock_coordinator = MagicMock()
    mock_coordinator.async_config_entry_first_refresh = AsyncMock()
    mock_coordinator.async_shutdown = AsyncMock()
    mock_coordinator.async_add_listener = MagicMock(return_value=lambda: None)
    mock_coordinator.ensure_telegram_listener = MagicMock()
    mock_coordinator.fire_device_event = MagicMock()
    mock_coordinator.register_transmitter_entities = MagicMock()
    mock_coordinator.unregister_transmitter_entity = MagicMock()
    mock_coordinator.register_sensor_entities = MagicMock()
    mock_coordinator.unregister_sensor_entity = MagicMock()
    mock_coordinator.transceiver = mock_transceiver
    mock_coordinator.is_offline = False
    mock_coordinator.data = {"is_connected": True, "device_path": "/dev/ttyACM0"}

    transceiver_patch = patch(
        "homeassistant.components.easywave.RX11Transceiver",
        return_value=mock_transceiver,
    )
    coordinator_patch = patch(
        "homeassistant.components.easywave.EasywaveCoordinator",
        return_value=mock_coordinator,
    )
    return transceiver_patch, coordinator_patch, mock_coordinator


async def test_sensor_setup_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test that sensor platform setup creates a gateway sensor entity."""
    mock_config_entry.add_to_hass(hass)
    hass.config.country = "DE"

    transceiver_patch, coordinator_patch, _ = _patch_integration()
    with transceiver_patch, coordinator_patch:
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

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
    mock_config_entry.add_to_hass(hass)
    hass.config.country = "DE"

    transceiver_patch, coordinator_patch, mock_coordinator = _patch_integration()
    with transceiver_patch, coordinator_patch:
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{mock_config_entry.entry_id}_rx11_gateway"
    )
    assert entity_id is not None

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    mock_coordinator.async_add_listener.call_args[0][0]()
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
    mock_config_entry.add_to_hass(hass)
    hass.config.country = "DE"

    transceiver_patch, coordinator_patch, mock_coordinator = _patch_integration()
    mock_coordinator.transceiver.is_connected = False
    mock_coordinator.data = {"is_connected": False, "device_path": "/dev/ttyACM0"}

    def _fire_device_event(
        easywave_device_id: str, event_type: str, **event_data: object
    ) -> None:
        device = dr.async_get(hass).async_get_device(
            identifiers={(DOMAIN, easywave_device_id)}
        )
        if device is None:
            return
        hass.bus.async_fire(
            EVENT_EASYWAVE,
            {"device_id": device.id, "type": event_type, **event_data},
        )

    mock_coordinator.fire_device_event = _fire_device_event

    with transceiver_patch, coordinator_patch:
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    events = async_capture_events(hass, EVENT_EASYWAVE)
    listener = mock_coordinator.async_add_listener.call_args[0][0]

    hass.bus.async_fire(EVENT_HOMEASSISTANT_STARTED)
    listener()
    await hass.async_block_till_done()

    entity_id = er.async_get(hass).async_get_entity_id(
        "sensor", DOMAIN, f"{mock_config_entry.entry_id}_rx11_gateway"
    )
    assert hass.states.get(entity_id).state == "disconnected"

    mock_coordinator.transceiver.is_connected = True
    mock_coordinator.is_offline = False
    listener()
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == "connected"
    assert len(events) == 1
    assert events[0].data["type"] == "gateway_connected"

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
