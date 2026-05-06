"""Tests for the SVS Subwoofer coordinator branches not covered by entity tests."""

from binascii import crc_hqx
from unittest.mock import AsyncMock, MagicMock, patch

from bleak.exc import BleakError
from bleak_retry_connector import BleakNotFoundError
import pytest

from homeassistant.components.svs_subwoofer.const import DOMAIN
from homeassistant.components.svs_subwoofer.coordinator import SVSSubwooferCoordinator
from homeassistant.components.svs_subwoofer.svs_protocol import FRAME_PREAMBLE
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ADDRESS, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from . import SVS_ADDRESS, SVS_NAME, async_init_integration

from tests.common import MockConfigEntry


@pytest.mark.parametrize(
    ("exc", "match"),
    [
        (BleakNotFoundError("not found"), "not found"),
        (TimeoutError("timeout"), "Timeout connecting"),
        (BleakError("nope"), "Failed to connect"),
    ],
)
async def test_connect_failure_modes(
    hass: HomeAssistant, exc: Exception, match: str
) -> None:
    """Each BLE error class is wrapped into a meaningful UpdateFailed."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=SVS_ADDRESS.lower(),
        data={CONF_ADDRESS: SVS_ADDRESS, CONF_NAME: SVS_NAME},
        title=SVS_NAME,
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.svs_subwoofer.coordinator."
            "async_ble_device_from_address",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.svs_subwoofer.coordinator.establish_connection",
            side_effect=exc,
        ),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_send_command_write_error_raises(
    hass: HomeAssistant, mock_bleak_client: MagicMock
) -> None:
    """If write_gatt_char raises BleakError, we surface HomeAssistantError."""
    await async_init_integration(hass)
    coordinator: SVSSubwooferCoordinator = hass.config_entries.async_loaded_entries(
        DOMAIN
    )[0].runtime_data

    mock_bleak_client.write_gatt_char = AsyncMock(side_effect=BleakError("boom"))

    with pytest.raises(HomeAssistantError, match="Failed to send"):
        await coordinator.async_send_command("VOLUME", -25)


async def test_send_command_unknown_param_raises(
    hass: HomeAssistant, mock_bleak_client: MagicMock
) -> None:
    """Encoding a bogus parameter surfaces HomeAssistantError."""
    await async_init_integration(hass)
    coordinator: SVSSubwooferCoordinator = hass.config_entries.async_loaded_entries(
        DOMAIN
    )[0].runtime_data

    with pytest.raises(HomeAssistantError, match="Failed to encode"):
        await coordinator.async_send_command("DOES_NOT_EXIST", 0)


async def test_send_command_clears_active_preset(
    hass: HomeAssistant, mock_bleak_client: MagicMock
) -> None:
    """Modifying a syncable param invalidates the active preset marker."""
    await async_init_integration(hass)
    coordinator: SVSSubwooferCoordinator = hass.config_entries.async_loaded_entries(
        DOMAIN
    )[0].runtime_data
    coordinator.data["ACTIVE_PRESET"] = 2

    await coordinator.async_send_command("VOLUME", -30)

    assert coordinator.data["ACTIVE_PRESET"] is None


async def test_load_preset_validates_range(
    hass: HomeAssistant, mock_bleak_client: MagicMock
) -> None:
    """async_load_preset rejects out-of-range numbers before touching BLE."""
    await async_init_integration(hass)
    coordinator: SVSSubwooferCoordinator = hass.config_entries.async_loaded_entries(
        DOMAIN
    )[0].runtime_data

    with pytest.raises(ValueError, match="Invalid preset number"):
        await coordinator.async_load_preset(0)
    with pytest.raises(ValueError, match="Invalid preset number"):
        await coordinator.async_load_preset(99)


async def test_save_preset_validates_range(
    hass: HomeAssistant, mock_bleak_client: MagicMock
) -> None:
    """async_save_preset rejects preset 4 (factory default) and out-of-range."""
    await async_init_integration(hass)
    coordinator: SVSSubwooferCoordinator = hass.config_entries.async_loaded_entries(
        DOMAIN
    )[0].runtime_data

    with pytest.raises(ValueError, match="Invalid preset number for save"):
        await coordinator.async_save_preset(4)
    with pytest.raises(ValueError, match="Invalid preset number for save"):
        await coordinator.async_save_preset(0)


async def test_save_preset_write_error(
    hass: HomeAssistant, mock_bleak_client: MagicMock
) -> None:
    """A BleakError during preset save surfaces HomeAssistantError."""
    await async_init_integration(hass)
    coordinator: SVSSubwooferCoordinator = hass.config_entries.async_loaded_entries(
        DOMAIN
    )[0].runtime_data

    mock_bleak_client.write_gatt_char = AsyncMock(side_effect=BleakError("nope"))
    with pytest.raises(HomeAssistantError, match="save preset 1"):
        await coordinator.async_save_preset(1)


async def test_save_preset_happy_path(
    hass: HomeAssistant, mock_bleak_client: MagicMock
) -> None:
    """async_save_preset writes a single PRESETLOADSAVE frame."""
    await async_init_integration(hass)
    coordinator: SVSSubwooferCoordinator = hass.config_entries.async_loaded_entries(
        DOMAIN
    )[0].runtime_data

    pre = mock_bleak_client.write_gatt_char.await_count
    await coordinator.async_save_preset(2)
    assert mock_bleak_client.write_gatt_char.await_count == pre + 1


async def test_notification_handler_decodes_into_data(
    hass: HomeAssistant, mock_bleak_client: MagicMock
) -> None:
    """A complete crafted frame routed through _notification_handler updates data."""
    await async_init_integration(hass)
    coordinator: SVSSubwooferCoordinator = hass.config_entries.async_loaded_entries(
        DOMAIN
    )[0].runtime_data

    # Build a READ_RESP frame carrying VOLUME=-25.
    encoded = ((int(10 * 25) ^ 0xFFFF) + 1).to_bytes(2, "little")
    body = (
        b"\x00\x00\x00\x00"
        + (4).to_bytes(4, "little")
        + (0x2C).to_bytes(2, "little")
        + len(encoded).to_bytes(2, "little")
        + encoded
    )
    head = (
        FRAME_PREAMBLE
        + b"\xf2\x00"
        + (1 + 2 + 2 + len(body) + 2).to_bytes(2, "little")
        + body
    )
    frame = head + crc_hqx(head, 0).to_bytes(2, "little")

    coordinator._notification_handler(MagicMock(), bytearray(frame))
    assert coordinator.data["VOLUME"] == -25


async def test_notification_handler_ignores_garbage(
    hass: HomeAssistant, mock_bleak_client: MagicMock
) -> None:
    """An unrecognized fragment is silently dropped."""
    await async_init_integration(hass)
    coordinator: SVSSubwooferCoordinator = hass.config_entries.async_loaded_entries(
        DOMAIN
    )[0].runtime_data
    snapshot = dict(coordinator.data)

    coordinator._notification_handler(MagicMock(), bytearray(b"\x99" * 4))
    assert coordinator.data == snapshot


async def test_request_refresh_data_no_op_when_disconnected(
    hass: HomeAssistant, mock_bleak_client: MagicMock
) -> None:
    """async_request_refresh_data does nothing while disconnected."""
    await async_init_integration(hass)
    coordinator: SVSSubwooferCoordinator = hass.config_entries.async_loaded_entries(
        DOMAIN
    )[0].runtime_data
    coordinator._connected = False

    pre = mock_bleak_client.write_gatt_char.await_count
    await coordinator.async_request_refresh_data()
    assert mock_bleak_client.write_gatt_char.await_count == pre


async def test_request_refresh_data_writes_when_connected(
    hass: HomeAssistant, mock_bleak_client: MagicMock
) -> None:
    """async_request_refresh_data writes the four MEMREAD frames when connected."""
    await async_init_integration(hass)
    coordinator: SVSSubwooferCoordinator = hass.config_entries.async_loaded_entries(
        DOMAIN
    )[0].runtime_data

    pre = mock_bleak_client.write_gatt_char.await_count
    await coordinator.async_request_refresh_data()
    assert mock_bleak_client.write_gatt_char.await_count >= pre + 4


async def test_ensure_writable_reconnect_failure(
    hass: HomeAssistant, mock_bleak_client: MagicMock
) -> None:
    """If reconnection fails, send_command surfaces HomeAssistantError, not UpdateFailed."""
    await async_init_integration(hass)
    coordinator: SVSSubwooferCoordinator = hass.config_entries.async_loaded_entries(
        DOMAIN
    )[0].runtime_data
    # Simulate a dropped connection AND a failing ble_device lookup so reconnect fails.
    coordinator._connected = False
    coordinator._client = None

    with (
        patch(
            "homeassistant.components.svs_subwoofer.coordinator."
            "async_ble_device_from_address",
            return_value=None,
        ),
        pytest.raises(HomeAssistantError, match="not found"),
    ):
        await coordinator.async_send_command("VOLUME", -25)


async def test_connect_is_idempotent(
    hass: HomeAssistant, mock_bleak_client: MagicMock
) -> None:
    """Calling _connect again when already connected returns immediately."""
    await async_init_integration(hass)
    coordinator: SVSSubwooferCoordinator = hass.config_entries.async_loaded_entries(
        DOMAIN
    )[0].runtime_data

    # Should not error and should not invoke establish_connection again
    await coordinator._connect()
    assert coordinator.is_connected is True


async def test_request_full_settings_handles_bleak_error(
    hass: HomeAssistant, mock_bleak_client: MagicMock
) -> None:
    """A BleakError during _request_full_settings is logged and the loop exits."""
    await async_init_integration(hass)
    coordinator: SVSSubwooferCoordinator = hass.config_entries.async_loaded_entries(
        DOMAIN
    )[0].runtime_data

    mock_bleak_client.write_gatt_char = AsyncMock(side_effect=BleakError("boom"))
    # Should NOT raise — caller is fire-and-forget
    await coordinator._request_full_settings()


async def test_get_device_id_caches(
    hass: HomeAssistant, mock_bleak_client: MagicMock
) -> None:
    """_get_device_id returns the cached value on subsequent calls."""
    await async_init_integration(hass)
    coordinator: SVSSubwooferCoordinator = hass.config_entries.async_loaded_entries(
        DOMAIN
    )[0].runtime_data

    first = coordinator._get_device_id()
    second = coordinator._get_device_id()
    assert first == second
    assert first is not None


async def test_disconnect_callback_marks_disconnected(
    hass: HomeAssistant, mock_bleak_client: MagicMock
) -> None:
    """The on-disconnect BLE callback flips connection state and resets state."""
    await async_init_integration(hass)
    coordinator: SVSSubwooferCoordinator = hass.config_entries.async_loaded_entries(
        DOMAIN
    )[0].runtime_data

    assert coordinator.is_connected is True
    coordinator._on_disconnect(mock_bleak_client)
    assert coordinator.is_connected is False
