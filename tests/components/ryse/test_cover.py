"""Test RYSE Cover entity behavior."""

from collections.abc import Callable
import logging
from typing import Any
from unittest.mock import AsyncMock, MagicMock

from bleak import BleakError
from bleak.backends.device import BLEDevice
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
from homeassistant.components.ryse.const import MANUFACTURER_NAME, SERVICE_UUID
from homeassistant.config_entries import SOURCE_REAUTH
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

from . import inject_ryse, make_advertisement

from tests.common import MockConfigEntry, async_fire_time_changed

DEVICE_ADDRESS = "AA:BB:CC:DD:EE:FF"
ENTITY_ID = "cover.test_device"
LOGGER_NAME = "homeassistant.components.ryse.cover"


def _disconnect_callback(client: MagicMock) -> Callable[[MagicMock], None]:
    """Return the GATT disconnect callback registered on *client*."""
    client.set_disconnected_callback.assert_called()
    return client.set_disconnected_callback.call_args[0][0]


async def async_see_shade(
    hass: HomeAssistant, ble_device: BLEDevice, token: bytes = b"\x01"
) -> None:
    """Inject a local advertisement so a dropped cover can reconnect."""
    inject_ryse(
        hass,
        ble_device,
        make_advertisement(pairing=False, service_data={SERVICE_UUID: token}),
    )
    await hass.async_block_till_done()


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
    assert entity_entry.unique_id == DEVICE_ADDRESS
    assert entity_entry.device_id

    device_entry = device_registry.async_get(entity_entry.device_id)
    assert device_entry
    assert device_entry.manufacturer == MANUFACTURER_NAME
    assert device_entry.model == "SmartShade BLE"
    assert (dr.CONNECTION_BLUETOOTH, DEVICE_ADDRESS) in device_entry.connections

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes[ATTR_SUPPORTED_FEATURES] == (
        CoverEntityFeature.OPEN
        | CoverEntityFeature.CLOSE
        | CoverEntityFeature.SET_POSITION
    )


async def test_cover_available_after_setup(
    hass: HomeAssistant,
    mock_device: MagicMock,
    setup_integration: MockConfigEntry,
) -> None:
    """Test the cover is available and requests position after pairing."""
    assert mock_device.client is not None
    assert mock_device.client.is_connected
    mock_device.send_get_position.assert_awaited_once()

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_CURRENT_POSITION) is None


async def test_cover_polls_connected_device_without_pairing(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_device: MagicMock,
    setup_integration: MockConfigEntry,
) -> None:
    """Test an already connected device is not paired again."""
    mock_device.pair.reset_mock()
    mock_device.send_get_position.reset_mock()

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
    """Test an out of range position clears cached cover state."""
    caplog.set_level(logging.WARNING, logger=LOGGER_NAME)
    mock_device.is_valid_position.side_effect = lambda position: 0 <= position <= 100

    await mock_device.update_callback(58)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes[ATTR_CURRENT_POSITION] == 42
    assert state.state == CoverState.OPEN

    await mock_device.update_callback(150)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.attributes.get(ATTR_CURRENT_POSITION) is None
    assert state.state == STATE_UNKNOWN
    assert "Invalid position value detected: 150" in caplog.text


async def test_poll_skips_get_position_when_cached(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_device: MagicMock,
    polled_cover: MockConfigEntry,
) -> None:
    """Test polling does not request position again when a valid cache exists."""
    await mock_device.update_callback(100)
    await hass.async_block_till_done()
    mock_device.send_get_position.reset_mock()

    await async_poll_device(hass, freezer)

    mock_device.send_get_position.assert_not_awaited()
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == CoverState.CLOSED
    assert state.attributes[ATTR_CURRENT_POSITION] == 0


async def test_poll_refreshes_invalid_cached_position(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_device: MagicMock,
    polled_cover: MockConfigEntry,
) -> None:
    """Test polling clears a cached position that later fails validation."""
    await mock_device.update_callback(100)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == CoverState.CLOSED
    assert state.attributes[ATTR_CURRENT_POSITION] == 0

    mock_device.send_get_position.reset_mock()
    mock_device.is_valid_position.return_value = False

    await async_poll_device(hass, freezer)

    mock_device.send_get_position.assert_awaited_once()
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_UNKNOWN
    assert state.attributes.get(ATTR_CURRENT_POSITION) is None


@pytest.mark.parametrize(
    (
        "service",
        "service_data",
        "method",
        "device_args",
    ),
    [
        (SERVICE_OPEN_COVER, {}, "send_open", ()),
        (SERVICE_CLOSE_COVER, {}, "send_close", ()),
        (
            SERVICE_SET_COVER_POSITION,
            {ATTR_POSITION: 75},
            "send_set_position",
            (25,),
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
) -> None:
    """Test cover actions send a command without optimistically updating state."""
    await mock_device.update_callback(50)
    await hass.async_block_till_done()

    await hass.services.async_call(
        COVER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID} | service_data,
        blocking=True,
    )

    getattr(mock_device, method).assert_awaited_once_with(*device_args)
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == CoverState.OPEN
    assert state.attributes[ATTR_CURRENT_POSITION] == 50


@pytest.mark.parametrize(
    "exception",
    [TimeoutError("t/o"), OSError("io err"), EOFError("eof"), BleakError("ble err")],
    ids=["timeout", "oserror", "eof", "bleak"],
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


@pytest.mark.parametrize(
    (
        "service",
        "service_data",
        "method",
        "device_args",
    ),
    [
        (SERVICE_OPEN_COVER, {}, "send_open", ()),
        (SERVICE_CLOSE_COVER, {}, "send_close", ()),
        (
            SERVICE_SET_COVER_POSITION,
            {ATTR_POSITION: 75},
            "send_set_position",
            (25,),
        ),
    ],
)
@pytest.mark.usefixtures("polled_cover")
async def test_cover_command_reconnects_when_disconnected(
    hass: HomeAssistant,
    mock_device: MagicMock,
    service: str,
    service_data: dict[str, Any],
    method: str,
    device_args: tuple[int, ...],
) -> None:
    """Test a cover command pairs again when the previous poll dropped the client."""
    mock_device.client = None
    mock_device.pair.reset_mock()

    await hass.services.async_call(
        COVER_DOMAIN,
        service,
        {ATTR_ENTITY_ID: ENTITY_ID} | service_data,
        blocking=True,
    )

    mock_device.pair.assert_awaited_once()
    getattr(mock_device, method).assert_awaited_once_with(*device_args)


@pytest.mark.parametrize(
    ("service", "service_data", "error"),
    [
        (SERVICE_OPEN_COVER, {}, "Failed to open cover: failed to pair"),
        (SERVICE_CLOSE_COVER, {}, "Failed to close cover: failed to pair"),
        (
            SERVICE_SET_COVER_POSITION,
            {ATTR_POSITION: 50},
            "Failed to set cover position: failed to pair",
        ),
    ],
)
async def test_cover_command_raises_when_reconnect_fails(
    hass: HomeAssistant,
    mock_device: MagicMock,
    polled_cover: MockConfigEntry,
    service: str,
    service_data: dict[str, Any],
    error: str,
) -> None:
    """Test a cover command surfaces an error instead of no-oping without a client."""
    mock_device.client = None
    mock_device.pair.side_effect = AsyncMock(return_value=False)
    mock_device.unpair.reset_mock()

    with pytest.raises(HomeAssistantError, match=error):
        await hass.services.async_call(
            COVER_DOMAIN,
            service,
            {ATTR_ENTITY_ID: ENTITY_ID} | service_data,
            blocking=True,
        )

    mock_device.send_open.assert_not_awaited()
    mock_device.send_close.assert_not_awaited()
    mock_device.send_set_position.assert_not_awaited()
    mock_device.unpair.assert_awaited_once()
    assert list(polled_cover.async_get_active_flows(hass, {SOURCE_REAUTH}))


async def test_pairing_failure_marks_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_device: MagicMock,
    caplog: pytest.LogCaptureFixture,
    polled_cover: MockConfigEntry,
) -> None:
    """Test a failed pairing marks the cover unavailable and is logged once."""
    caplog.set_level(logging.INFO, logger=LOGGER_NAME)
    mock_device.client = None
    mock_device.pair.side_effect = AsyncMock(return_value=False)
    mock_device.unpair.reset_mock()

    with pytest.raises(
        HomeAssistantError, match="Failed to open cover: failed to pair"
    ):
        await hass.services.async_call(
            COVER_DOMAIN,
            SERVICE_OPEN_COVER,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_UNAVAILABLE
    unavailable = f"{ENTITY_ID} became unavailable: failed to pair"
    assert caplog.text.count(unavailable) == 1
    mock_device.unpair.assert_awaited_once()
    assert list(polled_cover.async_get_active_flows(hass, {SOURCE_REAUTH}))

    caplog.clear()
    mock_device.pair.reset_mock()
    await async_poll_device(hass, freezer)

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_UNAVAILABLE
    assert unavailable not in caplog.text
    mock_device.pair.assert_not_awaited()


@pytest.mark.parametrize(
    "exception",
    [TimeoutError("t/o"), OSError("io err"), EOFError("eof"), BleakError("ble err")],
    ids=["timeout", "oserror", "eof", "bleak"],
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
    caplog.set_level(logging.INFO, logger=LOGGER_NAME)
    mock_device.send_get_position.side_effect = exception
    mock_device.unpair.reset_mock()

    await async_poll_device(hass, freezer)

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_UNAVAILABLE
    unavailable = f"{ENTITY_ID} became unavailable: {exception}"
    assert caplog.text.count(unavailable) == 1
    mock_device.unpair.assert_awaited_once()

    caplog.clear()
    mock_device.pair.reset_mock()
    await async_poll_device(hass, freezer)

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_UNAVAILABLE
    assert unavailable not in caplog.text
    mock_device.pair.assert_not_awaited()


async def test_ble_error_while_polling_clears_cached_position(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_device: MagicMock,
    local_ryse_scanner: BLEDevice,
    polled_cover: MockConfigEntry,
) -> None:
    """Test a poll error drops cached position so reconnect fetches again."""
    await mock_device.update_callback(50)
    await hass.async_block_till_done()

    mock_device.is_valid_position.return_value = False
    mock_device.send_get_position.side_effect = BleakError("ble err")
    mock_device.unpair.reset_mock()
    await async_poll_device(hass, freezer)

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_UNAVAILABLE
    assert state.attributes.get(ATTR_CURRENT_POSITION) is None
    mock_device.unpair.assert_awaited_once()

    mock_device.send_get_position.side_effect = None
    mock_device.send_get_position.reset_mock()
    await async_see_shade(hass, local_ryse_scanner)

    mock_device.send_get_position.assert_awaited_once()
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state != STATE_UNAVAILABLE


async def test_ble_error_while_polling_resets_connection(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_device: MagicMock,
    local_ryse_scanner: BLEDevice,
    polled_cover: MockConfigEntry,
) -> None:
    """Test a poll error unpairs and waits for an advertisement instead of pairing again."""
    mock_device.send_get_position.side_effect = BleakError("ble err")
    mock_device.unpair.reset_mock()
    mock_device.pair.reset_mock()

    await async_poll_device(hass, freezer)

    mock_device.unpair.assert_awaited_once()
    mock_device.pair.assert_not_awaited()

    mock_device.send_get_position.side_effect = None
    mock_device.send_get_position.reset_mock()
    mock_device.pair.reset_mock()
    await async_poll_device(hass, freezer)

    mock_device.pair.assert_not_awaited()
    mock_device.send_get_position.assert_not_awaited()

    await async_see_shade(hass, local_ryse_scanner)

    mock_device.pair.assert_awaited_once()
    mock_device.send_get_position.assert_awaited_once()
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state != STATE_UNAVAILABLE


async def test_disconnect_callback_marks_unavailable(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    mock_device: MagicMock,
    caplog: pytest.LogCaptureFixture,
    setup_integration: MockConfigEntry,
) -> None:
    """Test a GATT disconnect marks the cover unavailable without waiting to poll."""
    caplog.set_level(logging.INFO, logger=LOGGER_NAME)
    client = mock_device.client
    mock_device.pair.reset_mock()
    mock_device.unpair.reset_mock()

    _disconnect_callback(client)(client)
    await hass.async_block_till_done()

    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_UNAVAILABLE
    assert f"{ENTITY_ID} became unavailable: disconnected" in caplog.text
    mock_device.unpair.assert_awaited_once()
    mock_device.pair.assert_not_awaited()

    mock_device.pair.reset_mock()
    await async_poll_device(hass, freezer)

    mock_device.pair.assert_not_awaited()
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state == STATE_UNAVAILABLE


async def test_advertisement_reconnects_after_disconnect(
    hass: HomeAssistant,
    local_ryse_scanner: BLEDevice,
    mock_device: MagicMock,
    setup_integration: MockConfigEntry,
) -> None:
    """Test a later advertisement reconnects after the GATT link drops."""
    client = mock_device.client
    mock_device.pair.reset_mock()
    mock_device.send_get_position.reset_mock()
    mock_device.unpair.reset_mock()

    _disconnect_callback(client)(client)
    await hass.async_block_till_done()
    mock_device.pair.assert_not_awaited()

    await async_see_shade(hass, local_ryse_scanner)

    mock_device.pair.assert_awaited_once()
    mock_device.send_get_position.assert_awaited_once()
    state = hass.states.get(ENTITY_ID)
    assert state
    assert state.state != STATE_UNAVAILABLE


async def test_notification_callback_lifecycle(
    hass: HomeAssistant,
    mock_device: MagicMock,
    setup_integration: MockConfigEntry,
) -> None:
    """Test the device notification callback is registered and removed again."""
    assert callable(mock_device.update_callback)

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
