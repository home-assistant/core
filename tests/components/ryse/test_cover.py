"""Test RYSE Cover entity behavior."""

import logging
from typing import Any
from unittest.mock import MagicMock

from bleak import BleakError
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.cover import (
    ATTR_CURRENT_POSITION,
    ATTR_POSITION,
    DOMAIN as COVER_DOMAIN,
    SCAN_INTERVAL,
    CoverEntityFeature,
    CoverState,
)
from homeassistant.const import (
    ATTR_ENTITY_ID,
    ATTR_SUPPORTED_FEATURES,
    SERVICE_CLOSE_COVER,
    SERVICE_OPEN_COVER,
    SERVICE_SET_COVER_POSITION,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed

DEVICE_ADDRESS = "AA:BB:CC:DD:EE:FF"
ENTITY_ID = "cover.test_device"
LOGGER_NAME = "homeassistant.components.ryse.cover"


async def async_poll_device(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Advance time so the cover platform polls the device once."""
    freezer.tick(SCAN_INTERVAL)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


@pytest.fixture
async def polled_cover(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    setup_integration: MockConfigEntry,
) -> MockConfigEntry:
    """Set up the integration and let the cover complete its first poll."""
    await async_poll_device(hass, freezer)

    return setup_integration


async def test_cover_entity(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    polled_cover: MockConfigEntry,
) -> None:
    """Test the cover entity is registered against the RYSE device."""
    entity_entry = entity_registry.async_get(ENTITY_ID)
    assert entity_entry
    assert entity_entry.unique_id == f"{DEVICE_ADDRESS}_cover"
    assert entity_entry.device_id

    device_entry = device_registry.async_get(entity_entry.device_id)
    assert device_entry
    assert device_entry.manufacturer == "RYSE"
    assert device_entry.model == "SmartShade BLE"
    assert (dr.CONNECTION_BLUETOOTH, DEVICE_ADDRESS) in device_entry.connections

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.SET_POSITION
    )


async def test_cover_unavailable_until_first_poll(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_device: MagicMock,
    setup_integration: MockConfigEntry,
) -> None:
    """Test the cover stays unavailable until the device has been polled."""
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_UNAVAILABLE

    await async_poll_device(hass, freezer)

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_CURRENT_POSITION) is None
    mock_device.send_get_position.assert_awaited_once()


async def test_cover_polls_connected_device_without_pairing(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_device: MagicMock,
    setup_integration: MockConfigEntry,
) -> None:
    """Test an already connected device is not paired again."""
    mock_device.client = MagicMock(is_connected=True)

    await async_poll_device(hass, freezer)

    mock_device.pair.assert_not_awaited()
    mock_device.send_get_position.assert_awaited_once()
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state != STATE_UNAVAILABLE


async def test_position_notification(
    hass: HomeAssistant,
    mock_device: MagicMock,
    polled_cover: MockConfigEntry,
) -> None:
    """Test a position notification from the device updates the state machine."""
    await mock_device.update_callback(100)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == CoverState.CLOSED
    assert state.attributes[ATTR_CURRENT_POSITION] == 0


async def test_position_notification_out_of_range(
    hass: HomeAssistant,
    mock_device: MagicMock,
    caplog: pytest.LogCaptureFixture,
    polled_cover: MockConfigEntry,
) -> None:
    """Test an out of range position is not exposed to the state machine."""
    caplog.set_level(logging.WARNING, logger=LOGGER_NAME)

    await mock_device.update_callback(58)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes[ATTR_CURRENT_POSITION] == 42

    mock_device.is_valid_position.return_value = False
    await mock_device.update_callback(58)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes.get(ATTR_CURRENT_POSITION) is None
    assert "Invalid position value detected: 42" in caplog.text


@pytest.mark.parametrize(
    (
        "service",
        "service_data",
        "method",
        "device_args",
        "expected_state",
        "expected_position",
    ),
    [
        (SERVICE_OPEN_COVER, {}, "send_open", (), CoverState.OPEN, 100),
        (SERVICE_CLOSE_COVER, {}, "send_close", (), CoverState.CLOSED, 0),
        (
            SERVICE_SET_COVER_POSITION,
            {ATTR_POSITION: 75},
            "send_set_position",
            (25,),
            CoverState.OPEN,
            75,
        ),
    ],
)
async def test_cover_services(
    hass: HomeAssistant,
    mock_device: MagicMock,
    polled_cover: MockConfigEntry,
    service: str,
    service_data: dict[str, Any],
    method: str,
    device_args: tuple[int, ...],
    expected_state: CoverState,
    expected_position: int,
) -> None:
    """Test the cover actions send a command and report the new position."""
    await hass.services.async_call(
        COVER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID} | service_data,
        blocking=True,
    )

    getattr(mock_device, method).assert_awaited_once_with(*device_args)
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == expected_state
    assert state.attributes[ATTR_CURRENT_POSITION] == expected_position


@pytest.mark.parametrize(
    "exception",
    [TimeoutError("t/o"), OSError("io err"), BleakError("ble err")],
    ids=["timeout", "oserror", "bleak"],
)
@pytest.mark.parametrize(
    ("service", "service_data", "method", "error"),
    [
        (SERVICE_OPEN_COVER, {}, "send_open", "Failed to open cover"),
        (SERVICE_CLOSE_COVER, {}, "send_close", "Failed to close cover"),
        (
            SERVICE_SET_COVER_POSITION,
            {ATTR_POSITION: 50},
            "send_set_position",
            "Failed to set cover position",
        ),
    ],
)
async def test_cover_services_ble_error(
    hass: HomeAssistant,
    mock_device: MagicMock,
    polled_cover: MockConfigEntry,
    exception: Exception,
    service: str,
    service_data: dict[str, Any],
    method: str,
    error: str,
) -> None:
    """Test BLE errors during a cover action surface as HomeAssistantError."""
    getattr(mock_device, method).side_effect = exception

    with pytest.raises(HomeAssistantError, match=error):
        await hass.services.async_call(
            COVER_DOMAIN,
            service,
            {ATTR_ENTITY_ID: ENTITY_ID} | service_data,
            blocking=True,
        )

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes.get(ATTR_CURRENT_POSITION) is None


async def test_pairing_failure_marks_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_device: MagicMock,
    caplog: pytest.LogCaptureFixture,
    polled_cover: MockConfigEntry,
) -> None:
    """Test a failed pairing marks the cover unavailable and is logged once."""
    caplog.set_level(logging.DEBUG, logger=LOGGER_NAME)
    mock_device.pair.return_value = False

    await async_poll_device(hass, freezer)

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_UNAVAILABLE
    assert "Failed to pair with device, skipping update" in caplog.text

    caplog.clear()
    await async_poll_device(hass, freezer)

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_UNAVAILABLE
    assert "Failed to pair with device, skipping update" not in caplog.text


@pytest.mark.parametrize(
    "exception",
    [TimeoutError("t/o"), OSError("io err"), BleakError("ble err")],
    ids=["timeout", "oserror", "bleak"],
)
async def test_ble_error_while_polling_marks_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_device: MagicMock,
    caplog: pytest.LogCaptureFixture,
    polled_cover: MockConfigEntry,
    exception: Exception,
) -> None:
    """Test a BLE error while polling marks the cover unavailable."""
    caplog.set_level(logging.WARNING, logger=LOGGER_NAME)
    mock_device.send_get_position.side_effect = exception

    await async_poll_device(hass, freezer)

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_UNAVAILABLE
    assert "BLE communication error while reading device data" in caplog.text


async def test_notification_callback_lifecycle(
    hass: HomeAssistant,
    mock_device: MagicMock,
    setup_integration: MockConfigEntry,
) -> None:
    """Test the device notification callback is registered and removed again."""
    assert mock_device.update_callback is not None

    await hass.config_entries.async_unload(setup_integration.entry_id)
    await hass.async_block_till_done()

    assert mock_device.update_callback is None


async def test_notification_callback_replaced(
    hass: HomeAssistant,
    mock_device: MagicMock,
    setup_integration: MockConfigEntry,
) -> None:
    """Test unloading keeps a callback that was registered by someone else."""
    other_callback = MagicMock()
    mock_device.update_callback = other_callback

    await hass.config_entries.async_unload(setup_integration.entry_id)
    await hass.async_block_till_done()

    assert mock_device.update_callback is other_callback
