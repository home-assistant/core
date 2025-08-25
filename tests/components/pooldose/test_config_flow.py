"""Test the PoolDose config flow."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.pooldose.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import RequestStatus

from tests.common import MockConfigEntry, async_load_fixture


async def test_form_shows_and_creates_entry(hass: HomeAssistant) -> None:
    """Test that the form is shown and entry is created on valid input."""
    # Mock successful client setup
    mock_client = MagicMock()
    device_info_raw = await async_load_fixture(hass, "deviceinfo.json", DOMAIN)
    device_info = json.loads(device_info_raw)
    mock_client.device_info = device_info
    mock_client.connect = AsyncMock(return_value=RequestStatus.SUCCESS)
    mock_client.check_apiversion_supported = MagicMock(
        return_value=(RequestStatus.SUCCESS, {})
    )
    mock_client.is_connected = True

    with patch(
        "homeassistant.components.pooldose.config_flow.PooldoseClient",
        return_value=mock_client,
    ):
        # Start flow
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "user"

        # Submit form
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "192.168.1.100"},
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "PoolDose TEST123456789"
        assert result["data"] == {CONF_HOST: "192.168.1.100"}


async def test_form_cannot_connect_host_unreachable(hass: HomeAssistant) -> None:
    """Test that the form shows an error if the device is unreachable."""
    mock_client = MagicMock()
    mock_client.connect = AsyncMock(return_value=RequestStatus.HOST_UNREACHABLE)
    mock_client.is_connected = False

    with patch(
        "homeassistant.components.pooldose.config_flow.PooldoseClient",
        return_value=mock_client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "192.168.1.100"},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}


async def test_form_api_version_unsupported(hass: HomeAssistant) -> None:
    """Test that the form shows error when API version is unsupported."""
    mock_client = MagicMock()
    api_versions = {"api_version_is": "v0.9", "api_version_should": "v1.0"}
    mock_client.connect = AsyncMock(return_value=RequestStatus.SUCCESS)
    mock_client.check_apiversion_supported = MagicMock(
        return_value=(RequestStatus.API_VERSION_UNSUPPORTED, api_versions)
    )
    mock_client.is_connected = True

    with patch(
        "homeassistant.components.pooldose.config_flow.PooldoseClient",
        return_value=mock_client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "192.168.1.100"},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "api_not_supported"}


async def test_duplicate_entry_aborts(hass: HomeAssistant) -> None:
    """Test that the flow aborts if the device is already configured."""
    # Create existing entry
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="TEST123456789",
        data={CONF_HOST: "192.168.1.50"},
    )
    existing_entry.add_to_hass(hass)

    mock_client = MagicMock()
    device_info_raw = await async_load_fixture(hass, "deviceinfo.json", DOMAIN)
    device_info = json.loads(device_info_raw)
    mock_client.device_info = device_info
    mock_client.connect = AsyncMock(return_value=RequestStatus.SUCCESS)
    mock_client.check_apiversion_supported = MagicMock(
        return_value=(RequestStatus.SUCCESS, {})
    )
    mock_client.is_connected = True

    with patch(
        "homeassistant.components.pooldose.config_flow.PooldoseClient",
        return_value=mock_client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "192.168.1.100"},
        )
        assert result["type"] == FlowResultType.ABORT
        assert result["reason"] == "already_configured"


async def test_form_no_device_info(hass: HomeAssistant) -> None:
    """Test that the form shows error when device_info is None."""
    mock_client = MagicMock()
    mock_client.device_info = None
    mock_client.connect = AsyncMock(return_value=RequestStatus.SUCCESS)
    mock_client.check_apiversion_supported = MagicMock(
        return_value=(RequestStatus.SUCCESS, {})
    )
    mock_client.is_connected = True

    with patch(
        "homeassistant.components.pooldose.config_flow.PooldoseClient",
        return_value=mock_client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "192.168.1.100"},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "no_device_info"}


@pytest.mark.parametrize(
    ("client_status", "expected_error"),
    [
        (RequestStatus.HOST_UNREACHABLE, "cannot_connect"),
        (RequestStatus.PARAMS_FETCH_FAILED, "params_fetch_failed"),
        (RequestStatus.UNKNOWN_ERROR, "cannot_connect"),
    ],
)
async def test_form_connection_errors(
    hass: HomeAssistant, client_status: str, expected_error: str
) -> None:
    """Test form handles different connection error statuses."""
    mock_client = MagicMock()
    mock_client.connect = AsyncMock(return_value=client_status)
    mock_client.is_connected = False

    with patch(
        "homeassistant.components.pooldose.config_flow.PooldoseClient",
        return_value=mock_client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "192.168.1.100"},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": expected_error}


async def test_form_retry_after_error(hass: HomeAssistant) -> None:
    """Test that user can retry after connection error."""
    # Start flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    flow_id = result["flow_id"]

    # First attempt fails
    mock_client_fail = MagicMock()
    mock_client_fail.connect = AsyncMock(return_value=RequestStatus.HOST_UNREACHABLE)
    mock_client_fail.is_connected = False

    with patch(
        "homeassistant.components.pooldose.config_flow.PooldoseClient",
        return_value=mock_client_fail,
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={CONF_HOST: "192.168.1.100"},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "cannot_connect"}

    # Second attempt succeeds
    mock_client_success = MagicMock()
    device_info_raw = await async_load_fixture(hass, "deviceinfo.json", DOMAIN)
    device_info = json.loads(device_info_raw)
    mock_client_success.device_info = device_info
    mock_client_success.connect = AsyncMock(return_value=RequestStatus.SUCCESS)
    mock_client_success.check_apiversion_supported = MagicMock(
        return_value=(RequestStatus.SUCCESS, {})
    )
    mock_client_success.is_connected = True

    with patch(
        "homeassistant.components.pooldose.config_flow.PooldoseClient",
        return_value=mock_client_success,
    ):
        result = await hass.config_entries.flow.async_configure(
            flow_id,
            user_input={CONF_HOST: "192.168.1.100"},
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "PoolDose TEST123456789"


async def test_form_api_no_data_error(hass: HomeAssistant) -> None:
    """Test that the form shows error when API returns NO_DATA."""
    mock_client = MagicMock()
    mock_client.connect = AsyncMock(return_value=RequestStatus.SUCCESS)
    mock_client.check_apiversion_supported = MagicMock(
        return_value=(RequestStatus.NO_DATA, {})
    )
    mock_client.is_connected = True

    with patch(
        "homeassistant.components.pooldose.config_flow.PooldoseClient",
        return_value=mock_client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "192.168.1.100"},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "api_not_set"}


async def test_form_no_serial_number(hass: HomeAssistant) -> None:
    """Test that the form shows error when device_info has no serial number."""
    mock_client = MagicMock()
    # Device info without SERIAL_NUMBER
    device_info = {"NAME": "Pool Device", "MODEL": "POOL DOSE"}
    mock_client.device_info = device_info
    mock_client.connect = AsyncMock(return_value=RequestStatus.SUCCESS)
    mock_client.check_apiversion_supported = MagicMock(
        return_value=(RequestStatus.SUCCESS, {})
    )
    mock_client.is_connected = True

    with patch(
        "homeassistant.components.pooldose.config_flow.PooldoseClient",
        return_value=mock_client,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_HOST: "192.168.1.100"},
        )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"] == {"base": "no_serial_number"}
