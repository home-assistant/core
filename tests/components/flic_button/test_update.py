"""Tests for the Flic Button update entity."""

from __future__ import annotations

import struct
from unittest.mock import MagicMock

import pytest

from homeassistant.components.flic_button.const import (
    DUO_FIRMWARE_DATA_CHUNK_SIZE,
    FIRMWARE_HEADER_SIZE,
    OPCODE_FIRMWARE_UPDATE_DATA_DUO_IND,
    OPCODE_FIRMWARE_UPDATE_DATA_IND,
    OPCODE_FORCE_BT_DISCONNECT_IND,
    OPCODE_START_FIRMWARE_UPDATE_DUO_REQUEST,
    OPCODE_START_FIRMWARE_UPDATE_REQUEST,
    TWIST_OPCODE_START_FIRMWARE_UPDATE_REQUEST,
    TWIST_OPCODE_START_FIRMWARE_UPDATE_RESPONSE,
)
from homeassistant.components.flic_button.flic_protocol import (
    DuoFirmwareUpdateDataInd,
    DuoStartFirmwareUpdateRequest,
    FirmwareUpdateDataInd,
    FirmwareUpdateNotification,
    Flic2FirmwareUpdateDataInd,
    Flic2ForceBtDisconnectInd,
    Flic2StartFirmwareUpdateRequest,
    ForceBtDisconnectInd,
    StartFirmwareUpdateRequest,
    StartFirmwareUpdateResponse,
)
from homeassistant.components.flic_button.update import FlicFirmwareUpdateEntity
from homeassistant.components.update import DOMAIN as UPDATE_DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

TWIST_ENTITY_ID = "update.flic_twist_t12345_firmware"
FLIC2_ENTITY_ID = "update.flic_2_b12345_firmware"
DUO_ENTITY_ID = "update.flic_duo_d12345_firmware"


@pytest.fixture
def platforms() -> list[Platform]:
    """Override platforms to only load update."""
    return [Platform.UPDATE]


async def test_update_entity_created_for_twist(
    hass: HomeAssistant,
    init_twist_integration,
) -> None:
    """Test update entity is created for Twist devices."""
    state = hass.states.get(TWIST_ENTITY_ID)
    assert state is not None


async def test_update_entity_created_for_flic2(
    hass: HomeAssistant,
    init_integration,
) -> None:
    """Test update entity is created for Flic 2 devices."""
    states = hass.states.async_entity_ids(UPDATE_DOMAIN)
    assert len(states) == 1


async def test_update_entity_created_for_duo(
    hass: HomeAssistant,
    init_duo_integration,
) -> None:
    """Test update entity is created for Duo devices."""
    states = hass.states.async_entity_ids(UPDATE_DOMAIN)
    assert len(states) == 1


async def test_no_update_available(
    hass: HomeAssistant,
    mock_twist_coordinator: MagicMock,
    init_twist_integration,
) -> None:
    """Test state is off when no update available."""
    state = hass.states.get(TWIST_ENTITY_ID)
    assert state is not None
    # latest_firmware_version is None, so latest_version equals installed_version
    assert state.state == STATE_OFF


async def test_update_available(
    hass: HomeAssistant,
    mock_twist_coordinator: MagicMock,
    init_twist_integration,
) -> None:
    """Test state is on when firmware update is available."""
    mock_twist_coordinator.latest_firmware_version = 11
    mock_twist_coordinator.firmware_version = 10

    # Trigger entity state refresh via entity component
    entity_comp = hass.data["entity_components"][UPDATE_DOMAIN]
    entity = entity_comp.get_entity(TWIST_ENTITY_ID)
    assert entity is not None
    entity.async_write_ha_state()

    state = hass.states.get(TWIST_ENTITY_ID)
    assert state is not None
    assert state.state == STATE_ON


async def test_install_success(
    hass: HomeAssistant,
    mock_twist_coordinator: MagicMock,
    init_twist_integration,
) -> None:
    """Test successful firmware install."""
    mock_twist_coordinator.latest_firmware_version = 11

    await hass.services.async_call(
        UPDATE_DOMAIN,
        "install",
        {ATTR_ENTITY_ID: TWIST_ENTITY_ID},
        blocking=True,
    )

    mock_twist_coordinator.async_install_firmware.assert_awaited_once()


async def test_install_failure(
    hass: HomeAssistant,
    mock_twist_coordinator: MagicMock,
    init_twist_integration,
) -> None:
    """Test firmware install failure raises error."""
    mock_twist_coordinator.latest_firmware_version = 11
    mock_twist_coordinator.async_install_firmware.side_effect = HomeAssistantError(
        "Firmware update failed"
    )

    with pytest.raises(HomeAssistantError, match="Firmware update failed"):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            "install",
            {ATTR_ENTITY_ID: TWIST_ENTITY_ID},
            blocking=True,
        )


async def test_duo_install_success(
    hass: HomeAssistant,
    mock_duo_coordinator: MagicMock,
    init_duo_integration,
) -> None:
    """Test successful firmware install on Duo device."""
    mock_duo_coordinator.latest_firmware_version = 11

    states = hass.states.async_entity_ids(UPDATE_DOMAIN)
    assert len(states) == 1
    entity_id = states[0]

    await hass.services.async_call(
        UPDATE_DOMAIN,
        "install",
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mock_duo_coordinator.async_install_firmware.assert_awaited_once()


async def test_duo_install_failure(
    hass: HomeAssistant,
    mock_duo_coordinator: MagicMock,
    init_duo_integration,
) -> None:
    """Test firmware install failure on Duo device raises error."""
    mock_duo_coordinator.latest_firmware_version = 11
    mock_duo_coordinator.async_install_firmware.side_effect = HomeAssistantError(
        "Firmware update failed"
    )

    states = hass.states.async_entity_ids(UPDATE_DOMAIN)
    assert len(states) == 1
    entity_id = states[0]

    with pytest.raises(HomeAssistantError, match="Firmware update failed"):
        await hass.services.async_call(
            UPDATE_DOMAIN,
            "install",
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )


# =============================================================================
# Twist protocol message tests
# =============================================================================


def test_start_firmware_update_request_from_firmware_binary() -> None:
    """Test parsing firmware binary header into request."""
    # Build a minimal firmware binary: 76-byte header + 10 bytes compressed data
    iv = b"\x01\x02\x03\x04\x05\x06\x07\x08"
    length_uncompressed_words = 1024
    signature = bytes(64)
    compressed_data = bytes(10)

    firmware_binary = (
        iv + struct.pack("<I", length_uncompressed_words) + signature + compressed_data
    )
    assert len(firmware_binary) == FIRMWARE_HEADER_SIZE + 10

    request = StartFirmwareUpdateRequest.from_firmware_binary(firmware_binary)
    assert request.iv == iv
    assert request.length_uncompressed_words == length_uncompressed_words
    assert request.signature == signature
    assert request.length_compressed_bytes == 10


def test_start_firmware_update_request_to_bytes() -> None:
    """Test serializing StartFirmwareUpdateRequest."""
    iv = bytes(8)
    signature = bytes(64)

    request = StartFirmwareUpdateRequest(
        length_compressed_bytes=100,
        iv=iv,
        length_uncompressed_words=200,
        signature=signature,
        status_interval=2,
    )
    data = request.to_bytes()

    assert data[0] == TWIST_OPCODE_START_FIRMWARE_UPDATE_REQUEST
    assert struct.unpack("<I", data[1:5])[0] == 100  # length_compressed_bytes
    assert data[5:13] == iv
    assert struct.unpack("<I", data[13:17])[0] == 200  # length_uncompressed_words
    assert data[17:81] == signature
    assert struct.unpack("<H", data[81:83])[0] == 2  # status_interval


def test_start_firmware_update_request_short_binary() -> None:
    """Test that short firmware binary raises ValueError."""
    with pytest.raises(ValueError, match="Firmware binary too short"):
        StartFirmwareUpdateRequest.from_firmware_binary(bytes(50))


def test_start_firmware_update_response_new() -> None:
    """Test parsing response with start_pos=0 (new update)."""
    data = struct.pack("<Bi", TWIST_OPCODE_START_FIRMWARE_UPDATE_RESPONSE, 0)
    response = StartFirmwareUpdateResponse.from_bytes(data)
    assert response.start_pos == 0


def test_start_firmware_update_response_resume() -> None:
    """Test parsing response with start_pos>0 (resume)."""
    data = struct.pack("<Bi", TWIST_OPCODE_START_FIRMWARE_UPDATE_RESPONSE, 500)
    response = StartFirmwareUpdateResponse.from_bytes(data)
    assert response.start_pos == 500


def test_start_firmware_update_response_invalid() -> None:
    """Test parsing response with start_pos=-1 (invalid params)."""
    data = struct.pack("<Bi", TWIST_OPCODE_START_FIRMWARE_UPDATE_RESPONSE, -1)
    response = StartFirmwareUpdateResponse.from_bytes(data)
    assert response.start_pos == -1


def test_start_firmware_update_response_busy() -> None:
    """Test parsing response with start_pos=-2 (device busy)."""
    data = struct.pack("<Bi", TWIST_OPCODE_START_FIRMWARE_UPDATE_RESPONSE, -2)
    response = StartFirmwareUpdateResponse.from_bytes(data)
    assert response.start_pos == -2


def test_start_firmware_update_response_pending_reboot() -> None:
    """Test parsing response with start_pos=-3 (pending reboot)."""
    data = struct.pack("<Bi", TWIST_OPCODE_START_FIRMWARE_UPDATE_RESPONSE, -3)
    response = StartFirmwareUpdateResponse.from_bytes(data)
    assert response.start_pos == -3


def test_start_firmware_update_response_short() -> None:
    """Test that short response raises ValueError."""
    with pytest.raises(ValueError, match="Invalid StartFirmwareUpdateResponse"):
        StartFirmwareUpdateResponse.from_bytes(bytes(3))


def test_firmware_update_notification_progress() -> None:
    """Test parsing progress notification."""
    data = struct.pack("<Bi", 0x0F, 240)
    notification = FirmwareUpdateNotification.from_bytes(data)
    assert notification.pos == 240


def test_firmware_update_notification_complete() -> None:
    """Test parsing completion notification."""
    data = struct.pack("<Bi", 0x0F, 1000)
    notification = FirmwareUpdateNotification.from_bytes(data)
    assert notification.pos == 1000


def test_firmware_update_notification_signature_fail() -> None:
    """Test parsing signature failure notification (pos=0)."""
    data = struct.pack("<Bi", 0x0F, 0)
    notification = FirmwareUpdateNotification.from_bytes(data)
    assert notification.pos == 0


def test_firmware_update_notification_short() -> None:
    """Test that short notification raises ValueError."""
    with pytest.raises(ValueError, match="Invalid FirmwareUpdateNotification"):
        FirmwareUpdateNotification.from_bytes(bytes(3))


def test_firmware_update_data_ind_to_bytes() -> None:
    """Test serializing firmware data chunk."""
    chunk = b"\xaa\xbb\xcc\xdd"
    data_ind = FirmwareUpdateDataInd(chunk_data=chunk)
    data = data_ind.to_bytes()
    assert data[0] == 0x10  # TWIST_OPCODE_FIRMWARE_UPDATE_DATA_IND
    assert data[1:] == chunk


def test_force_bt_disconnect_ind_to_bytes() -> None:
    """Test serializing force disconnect indication."""
    ind = ForceBtDisconnectInd(restart_adv=True)
    data = ind.to_bytes()
    assert data[0] == 0x06  # TWIST_OPCODE_FORCE_BT_DISCONNECT_IND
    assert data[1] == 1

    ind_no_adv = ForceBtDisconnectInd(restart_adv=False)
    data_no_adv = ind_no_adv.to_bytes()
    assert data_no_adv[1] == 0


# =============================================================================
# Flic 2 protocol message tests
# =============================================================================


def test_flic2_start_firmware_update_request_from_binary() -> None:
    """Test creating Flic 2 firmware update request from binary."""
    # Flic 2 binary: 8-byte IV + compressed data
    iv = b"\x01\x02\x03\x04\x05\x06\x07\x08"
    compressed_data = bytes(120)  # 120 bytes = 30 words

    firmware_binary = iv + compressed_data
    request = Flic2StartFirmwareUpdateRequest.from_firmware_binary(
        firmware_binary, connection_id=5
    )

    assert request.iv == iv
    assert request.length_compressed_words == 30  # 120 / 4
    assert request.connection_id == 5


def test_flic2_start_firmware_update_request_to_bytes() -> None:
    """Test serializing Flic2StartFirmwareUpdateRequest."""
    iv = bytes(8)
    request = Flic2StartFirmwareUpdateRequest(
        connection_id=3,
        length_compressed_words=100,
        iv=iv,
        status_interval=60,
    )
    data = request.to_bytes()

    assert data[0] == 3  # frame header (connection_id)
    assert data[1] == OPCODE_START_FIRMWARE_UPDATE_REQUEST
    assert struct.unpack("<H", data[2:4])[0] == 100  # length in words
    assert data[4:12] == iv
    assert struct.unpack("<H", data[12:14])[0] == 60  # status_interval


def test_flic2_start_firmware_update_request_short_binary() -> None:
    """Test that short Flic 2 firmware binary raises ValueError."""
    with pytest.raises(ValueError, match="Firmware binary too short"):
        Flic2StartFirmwareUpdateRequest.from_firmware_binary(bytes(4))


def test_flic2_start_firmware_update_request_word_rounding() -> None:
    """Test that compressed data length truncates partial words."""
    iv = bytes(8)
    # 13 bytes of data -> 3 words (floor(13/4)), trailing bytes dropped
    compressed_data = bytes(13)
    firmware_binary = iv + compressed_data
    request = Flic2StartFirmwareUpdateRequest.from_firmware_binary(firmware_binary)
    assert request.length_compressed_words == 3


def test_flic2_firmware_update_data_ind_to_bytes() -> None:
    """Test serializing Flic 2 firmware data indication."""
    words = [0x11223344, 0x55667788, 0x99AABBCC]
    data_ind = Flic2FirmwareUpdateDataInd(connection_id=2, words=words)
    data = data_ind.to_bytes()

    assert data[0] == 2  # frame header
    assert data[1] == OPCODE_FIRMWARE_UPDATE_DATA_IND
    assert struct.unpack("<I", data[2:6])[0] == 0x11223344
    assert struct.unpack("<I", data[6:10])[0] == 0x55667788
    assert struct.unpack("<I", data[10:14])[0] == 0x99AABBCC
    assert len(data) == 2 + 3 * 4  # header + opcode + 3 words


def test_flic2_force_bt_disconnect_ind_to_bytes() -> None:
    """Test serializing Flic 2 force disconnect indication."""
    ind = Flic2ForceBtDisconnectInd(connection_id=4, restart_adv=True)
    data = ind.to_bytes()

    assert data[0] == 4  # frame header
    assert data[1] == OPCODE_FORCE_BT_DISCONNECT_IND
    assert data[2] == 1  # restart_adv

    ind_no_adv = Flic2ForceBtDisconnectInd(connection_id=4, restart_adv=False)
    data_no_adv = ind_no_adv.to_bytes()
    assert data_no_adv[2] == 0


# =============================================================================
# Flic Duo protocol message tests
# =============================================================================


def test_duo_start_firmware_update_request_from_binary() -> None:
    """Test creating Duo firmware update request from binary."""
    # Duo binary: 76-byte header + compressed data (same as Twist)
    iv = b"\x01\x02\x03\x04\x05\x06\x07\x08"
    length_uncompressed_words = 1024
    signature = bytes(64)
    compressed_data = bytes(200)

    firmware_binary = (
        iv + struct.pack("<I", length_uncompressed_words) + signature + compressed_data
    )
    request = DuoStartFirmwareUpdateRequest.from_firmware_binary(
        firmware_binary, connection_id=7
    )

    assert request.firmware_header == firmware_binary[:FIRMWARE_HEADER_SIZE]
    assert request.length_compressed_bytes == 200
    assert request.connection_id == 7


def test_duo_start_firmware_update_request_to_bytes() -> None:
    """Test serializing DuoStartFirmwareUpdateRequest."""
    firmware_header = bytes(76)
    request = DuoStartFirmwareUpdateRequest(
        connection_id=5,
        length_compressed_bytes=300,
        firmware_header=firmware_header,
        status_interval=2,
    )
    data = request.to_bytes()

    assert data[0] == 5  # frame header
    assert data[1] == OPCODE_START_FIRMWARE_UPDATE_DUO_REQUEST
    assert struct.unpack("<I", data[2:6])[0] == 300  # length
    assert data[6:82] == firmware_header  # 76-byte header
    assert struct.unpack("<H", data[82:84])[0] == 2  # status_interval


def test_duo_start_firmware_update_request_short_binary() -> None:
    """Test that short Duo firmware binary raises ValueError."""
    with pytest.raises(ValueError, match="Firmware binary too short"):
        DuoStartFirmwareUpdateRequest.from_firmware_binary(bytes(50))


def test_duo_firmware_update_data_ind_to_bytes() -> None:
    """Test serializing Duo firmware data indication."""
    chunk = b"\xaa\xbb\xcc\xdd\xee"
    data_ind = DuoFirmwareUpdateDataInd(connection_id=3, chunk_data=chunk)
    data = data_ind.to_bytes()

    assert data[0] == 3  # frame header
    assert data[1] == OPCODE_FIRMWARE_UPDATE_DATA_DUO_IND
    assert data[2:] == chunk


def test_duo_firmware_update_data_ind_max_chunk() -> None:
    """Test Duo firmware data indication with max chunk size."""
    chunk = bytes(DUO_FIRMWARE_DATA_CHUNK_SIZE)
    data_ind = DuoFirmwareUpdateDataInd(connection_id=0, chunk_data=chunk)
    data = data_ind.to_bytes()

    assert len(data) == 2 + DUO_FIRMWARE_DATA_CHUNK_SIZE


# =============================================================================
# version_is_newer tests
# =============================================================================


@pytest.mark.parametrize(
    ("latest", "installed", "expected"),
    [
        ("11", "10", True),
        ("9", "10", False),
        ("10", "10", False),
        ("10+update", "10", True),
        ("abc", "10", False),
    ],
    ids=["newer", "older", "same", "update_suffix", "invalid"],
)
def test_version_is_newer(latest: str, installed: str, expected: bool) -> None:
    """Test version_is_newer compares firmware versions correctly."""
    assert (
        FlicFirmwareUpdateEntity.version_is_newer(None, latest, installed) is expected
    )
