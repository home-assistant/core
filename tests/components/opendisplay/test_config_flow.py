"""Test the OpenDisplay config flow."""

from unittest.mock import AsyncMock, patch

from opendisplay import BLEConnectionError, BLETimeoutError, OpenDisplayError
import pytest

from homeassistant import config_entries
from homeassistant.components.opendisplay.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import FIRMWARE_VERSION, NOT_OPENDISPLAY_SERVICE_INFO, VALID_SERVICE_INFO

from tests.common import MockConfigEntry


def _mock_open_display_device() -> AsyncMock:
    """Create a mock OpenDisplayDevice context manager."""
    mock_device = AsyncMock()
    mock_device.read_firmware_version = AsyncMock(return_value=FIRMWARE_VERSION)
    mock_device.__aenter__ = AsyncMock(return_value=mock_device)
    mock_device.__aexit__ = AsyncMock(return_value=False)
    return mock_device


def _patch_device(mock_device: AsyncMock | None = None):
    """Patch OpenDisplayDevice constructor."""
    if mock_device is None:
        mock_device = _mock_open_display_device()
    return patch(
        "homeassistant.components.opendisplay.config_flow.OpenDisplayDevice",
        return_value=mock_device,
    )


def _patch_ble_device():
    """Patch async_ble_device_from_address to return a mock BLE device."""
    return patch(
        "homeassistant.components.opendisplay.config_flow.async_ble_device_from_address",
        return_value=VALID_SERVICE_INFO.device,
    )


def _patch_ble_device_not_found():
    """Patch async_ble_device_from_address to return None."""
    return patch(
        "homeassistant.components.opendisplay.config_flow.async_ble_device_from_address",
        return_value=None,
    )


# --- Bluetooth discovery tests ---


async def test_bluetooth_discovery(hass: HomeAssistant) -> None:
    """Test discovery via Bluetooth with a valid device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=VALID_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    with (
        _patch_ble_device(),
        _patch_device(),
        patch(
            "homeassistant.components.opendisplay.async_setup_entry",
            return_value=True,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "OpenDisplay 1234"
    assert result2["data"] == {}
    assert result2["result"].unique_id == "AA:BB:CC:DD:EE:FF"


async def test_bluetooth_discovery_already_configured(hass: HomeAssistant) -> None:
    """Test discovery aborts when device is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="AA:BB:CC:DD:EE:FF",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=VALID_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_bluetooth_discovery_already_in_progress(hass: HomeAssistant) -> None:
    """Test discovery aborts when same device flow is in progress."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=VALID_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM

    result2 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=VALID_SERVICE_INFO,
    )
    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_in_progress"


# --- Bluetooth confirm error tests ---


@pytest.mark.parametrize(
    "exception",
    [BLEConnectionError("test"), BLETimeoutError("test"), OpenDisplayError("test")],
)
async def test_bluetooth_confirm_connection_error(
    hass: HomeAssistant, exception: Exception
) -> None:
    """Test confirm step handles connection errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=VALID_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM

    mock_device = _mock_open_display_device()
    mock_device.__aenter__.side_effect = exception

    with _patch_ble_device(), _patch_device(mock_device):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_bluetooth_confirm_ble_device_not_found(
    hass: HomeAssistant,
) -> None:
    """Test confirm step when BLE device is not found."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=VALID_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM

    with _patch_ble_device_not_found():
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={}
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


# --- User step tests ---


async def test_user_step_with_devices(hass: HomeAssistant) -> None:
    """Test user step with discovered devices."""
    with patch(
        "homeassistant.components.opendisplay.config_flow.async_discovered_service_info",
        return_value=[VALID_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with (
        _patch_ble_device(),
        _patch_device(),
        patch(
            "homeassistant.components.opendisplay.async_setup_entry",
            return_value=True,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"address": "AA:BB:CC:DD:EE:FF"},
        )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "OpenDisplay 1234"
    assert result2["data"] == {}
    assert result2["result"].unique_id == "AA:BB:CC:DD:EE:FF"


async def test_user_step_no_devices(hass: HomeAssistant) -> None:
    """Test user step when no devices are discovered."""
    with patch(
        "homeassistant.components.opendisplay.config_flow.async_discovered_service_info",
        return_value=[],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_user_step_filters_unsupported(hass: HomeAssistant) -> None:
    """Test user step filters out unsupported devices."""
    with patch(
        "homeassistant.components.opendisplay.config_flow.async_discovered_service_info",
        return_value=[NOT_OPENDISPLAY_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"


async def test_user_step_connection_error(hass: HomeAssistant) -> None:
    """Test user step handles connection errors."""
    with patch(
        "homeassistant.components.opendisplay.config_flow.async_discovered_service_info",
        return_value=[VALID_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

    assert result["type"] is FlowResultType.FORM

    mock_device = _mock_open_display_device()
    mock_device.__aenter__.side_effect = BLEConnectionError("test")

    with _patch_ble_device(), _patch_device(mock_device):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={"address": "AA:BB:CC:DD:EE:FF"},
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_user_step_already_configured(hass: HomeAssistant) -> None:
    """Test user step aborts when device is already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="AA:BB:CC:DD:EE:FF",
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.opendisplay.config_flow.async_discovered_service_info",
        return_value=[VALID_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

    # Device is filtered out since it's already configured
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_devices_found"
