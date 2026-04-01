"""Test the OpenDisplay config flow."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

from opendisplay import BLEConnectionError, BLETimeoutError, OpenDisplayError
import pytest

from homeassistant import config_entries
from homeassistant.components.opendisplay.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import NOT_OPENDISPLAY_SERVICE_INFO, VALID_SERVICE_INFO

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def mock_setup_entry() -> Generator[None]:
    """Prevent the integration from actually setting up after config flow."""
    with patch(
        "homeassistant.components.opendisplay.async_setup_entry",
        return_value=True,
    ):
        yield


async def test_bluetooth_discovery(hass: HomeAssistant) -> None:
    """Test discovery via Bluetooth with a valid device."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=VALID_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bluetooth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "OpenDisplay 1234"
    assert result["data"] == {}
    assert result["result"].unique_id == "AA:BB:CC:DD:EE:FF"


async def test_bluetooth_discovery_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test discovery aborts when device is already configured."""
    mock_config_entry.add_to_hass(hass)

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

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=VALID_SERVICE_INFO,
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_in_progress"


@pytest.mark.parametrize(
    ("exception", "expected_reason"),
    [
        (BLEConnectionError("test"), "cannot_connect"),
        (BLETimeoutError("test"), "cannot_connect"),
        (OpenDisplayError("test"), "cannot_connect"),
        (RuntimeError("test"), "unknown"),
    ],
)
async def test_bluetooth_confirm_connection_error(
    hass: HomeAssistant,
    mock_opendisplay_device: MagicMock,
    exception: Exception,
    expected_reason: str,
) -> None:
    """Test confirm step aborts when connection fails before showing the form."""
    mock_opendisplay_device.__aenter__.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_BLUETOOTH},
        data=VALID_SERVICE_INFO,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == expected_reason


async def test_bluetooth_confirm_ble_device_not_found(
    hass: HomeAssistant,
) -> None:
    """Test confirm step aborts when BLE device is not found."""
    with patch(
        "homeassistant.components.opendisplay.config_flow.async_ble_device_from_address",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_BLUETOOTH},
            data=VALID_SERVICE_INFO,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


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

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"address": "AA:BB:CC:DD:EE:FF"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "OpenDisplay 1234"
    assert result["data"] == {}
    assert result["result"].unique_id == "AA:BB:CC:DD:EE:FF"


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


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (BLEConnectionError("test"), "cannot_connect"),
        (BLETimeoutError("test"), "cannot_connect"),
        (OpenDisplayError("test"), "cannot_connect"),
        (RuntimeError("test"), "unknown"),
    ],
)
async def test_user_step_connection_error(
    hass: HomeAssistant,
    mock_opendisplay_device: MagicMock,
    exception: Exception,
    expected_error: str,
) -> None:
    """Test user step handles connection and unexpected errors."""
    with patch(
        "homeassistant.components.opendisplay.config_flow.async_discovered_service_info",
        return_value=[VALID_SERVICE_INFO],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
        )

    assert result["type"] is FlowResultType.FORM

    mock_opendisplay_device.__aenter__.side_effect = exception
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"address": "AA:BB:CC:DD:EE:FF"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    mock_opendisplay_device.__aenter__.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={"address": "AA:BB:CC:DD:EE:FF"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_step_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test user step aborts when device is already configured."""
    mock_config_entry.add_to_hass(hass)

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
