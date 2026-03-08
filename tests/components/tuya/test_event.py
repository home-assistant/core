"""Test Tuya event platform."""

from __future__ import annotations

import base64
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from tuya_sharing import CustomerDevice, Manager

from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MockDeviceListener, initialize_entry

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.freeze_time("2023-11-01 13:14:15+01:00")
@patch("homeassistant.components.tuya.PLATFORMS", [Platform.EVENT])
async def test_platform_setup_and_discovery(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_devices: list[CustomerDevice],
    mock_listener: MockDeviceListener,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test platform setup and discovery."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_devices)

    for mock_device in mock_devices:
        # Simulate an initial device update to generate events
        await mock_listener.async_send_device_update(
            hass, mock_device, mock_device.status
        )

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.parametrize(
    "mock_device_code",
    ["sp_csr2fqitalj5o0tq"],
)
@pytest.mark.parametrize(
    ("entity_id", "dpcode", "value"),
    [
        (
            "event.intercom_doorbell_picture",
            "doorbell_pic",
            base64.b64encode(b"https://some-picture-url.com/image.jpg"),
        ),
        (
            "event.intercom_doorbell_message",
            "alarm_message",
            base64.b64encode(b'{"some": "json", "random": "data"}'),
        ),
    ],
)
@patch("homeassistant.components.tuya.PLATFORMS", [Platform.EVENT])
async def test_alarm_message_event(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    mock_listener: MockDeviceListener,
    snapshot: SnapshotAssertion,
    entity_id: str,
    dpcode: str,
    value: str,
) -> None:
    """Test alarm message event."""
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    mock_device.status[dpcode] = value

    await mock_listener.async_send_device_update(hass, mock_device, mock_device.status)

    # Verify event was triggered with correct type and decoded URL
    state = hass.states.get(entity_id)
    assert state.attributes == snapshot
    assert state.attributes["message"]


@pytest.mark.parametrize(
    "mock_device_code",
    ["wxkg_l8yaz4um5b3pwyvf"],
)
@patch("homeassistant.components.tuya.PLATFORMS", [Platform.EVENT])
@pytest.mark.freeze_time("2024-01-01")
async def test_selective_state_update(
    hass: HomeAssistant,
    mock_manager: Manager,
    mock_config_entry: MockConfigEntry,
    mock_device: CustomerDevice,
    mock_listener: MockDeviceListener,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Ensure event is only triggered when device reports actual data."""
    entity_id = "event.bathroom_smart_switch_button_1"
    await initialize_entry(hass, mock_manager, mock_config_entry, mock_device)

    # Initial state is unknown
    assert hass.states.get(entity_id).state == STATE_UNKNOWN

    # Device receives a data update - event gets triggered and state gets updated
    freezer.tick(10)
    await mock_listener.async_send_device_update(
        hass, mock_device, {"switch_mode1": "click"}
    )
    assert hass.states.get(entity_id).state == "2024-01-01T00:00:10.000+00:00"

    # Device goes offline
    freezer.tick(10)
    mock_device.online = False
    await mock_listener.async_send_device_update(hass, mock_device, None)
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    # Device comes back online - state should go back to last known value,
    # not new datetime since no new data update has come in
    freezer.tick(10)
    mock_device.online = True
    await mock_listener.async_send_device_update(hass, mock_device, None)
    assert hass.states.get(entity_id).state == "2024-01-01T00:00:10.000+00:00"

    # Device receives a new data update - event gets triggered and state gets updated
    freezer.tick(10)
    await mock_listener.async_send_device_update(
        hass, mock_device, {"switch_mode1": "click"}
    )
    assert hass.states.get(entity_id).state == "2024-01-01T00:00:40.000+00:00"

    # Device receives a data update on a different datapoint - event doesn't
    # get triggered and state doesn't get updated
    freezer.tick(10)
    await mock_listener.async_send_device_update(
        hass, mock_device, {"switch_mode2": "click"}
    )
    assert hass.states.get(entity_id).state == "2024-01-01T00:00:40.000+00:00"
