"""Define tests for the Lunatone config flow."""

from collections.abc import Generator
from typing import Final
from unittest.mock import AsyncMock, patch

import aiohttp
from lunatone_rest_api_client.discovery import (
    LunatoneDiscoveryInfo,
    LunatoneDiscoveryType,
)
import pytest

from homeassistant.components.lunatone.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_DEVICE, CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import BASE_URL, SERIAL_NUMBER

from tests.common import MockConfigEntry

DISCOVERED_DEVICES: Final[list[LunatoneDiscoveryInfo]] = [
    LunatoneDiscoveryInfo(
        host="10.0.0.1", name="Device1", type=LunatoneDiscoveryType.DALI2_IOT
    ),
    LunatoneDiscoveryInfo(
        host="10.0.0.2", name="Device2", type=LunatoneDiscoveryType.DALI2_IOT
    ),
    LunatoneDiscoveryInfo(
        host="10.0.0.3", name="Device3", type=LunatoneDiscoveryType.DALI2_IOT
    ),
]


@pytest.fixture
def mock_discover_devices() -> Generator[AsyncMock]:
    """Mock the async_discover_devices function."""
    with patch(
        "homeassistant.components.lunatone.config_flow.async_discover_devices"
    ) as mock_discover:
        mock_discover.return_value = []
        yield mock_discover


async def test_full_flow(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_discover_devices: AsyncMock,
) -> None:
    """Test full user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "url_input"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: BASE_URL},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Test {SERIAL_NUMBER}"
    assert result["data"] == {CONF_URL: BASE_URL}


async def test_full_flow_with_discovered_devices(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_discover_devices: AsyncMock,
) -> None:
    """Test full user flow with discovered devices."""
    mock_discover_devices.return_value = DISCOVERED_DEVICES
    selected_host = "10.0.0.2"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_device"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DEVICE: selected_host}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Test {SERIAL_NUMBER}"
    assert result["data"] == {CONF_URL: f"http://{selected_host}"}


async def test_full_flow_with_discovered_devices_and_manual_url(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_setup_entry: AsyncMock,
    mock_discover_devices: AsyncMock,
) -> None:
    """Test full user flow with discovered devices."""
    mock_discover_devices.return_value = DISCOVERED_DEVICES
    selected_host = "10.0.0.2"

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "select_device"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_DEVICE: "__manual__"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "url_input"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: f"http://{selected_host}"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Test {SERIAL_NUMBER}"
    assert result["data"] == {CONF_URL: f"http://{selected_host}"}


async def test_full_flow_fail_because_of_missing_device_infos(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_discover_devices: AsyncMock,
) -> None:
    """Test full flow."""
    mock_lunatone_info.data = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "url_input"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: BASE_URL},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "url_input"
    assert result["errors"] == {"base": "missing_device_info"}


async def test_device_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_discover_devices: AsyncMock,
) -> None:
    """Test that the flow is aborted when the device is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "url_input"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_URL: BASE_URL},
    )

    assert result2.get("type") is FlowResultType.ABORT
    assert result2.get("reason") == "already_configured"


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (aiohttp.InvalidUrlClientError(BASE_URL), "invalid_url"),
        (aiohttp.ClientConnectionError(), "cannot_connect"),
    ],
)
async def test_user_step_fail_with_error(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_discover_devices: AsyncMock,
    exception: Exception,
    expected_error: str,
) -> None:
    """Test user step with an error."""
    mock_lunatone_info.async_update.side_effect = exception

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "url_input"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: BASE_URL},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    mock_lunatone_info.async_update.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: BASE_URL},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Test {SERIAL_NUMBER}"
    assert result["data"] == {CONF_URL: BASE_URL}


async def test_reconfigure(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_discover_devices: AsyncMock,
) -> None:
    """Test reconfigure flow."""
    url = "http://10.0.0.100"

    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "url_input"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: url}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {CONF_URL: url}


@pytest.mark.parametrize(
    ("exception", "expected_error"),
    [
        (aiohttp.InvalidUrlClientError(BASE_URL), "invalid_url"),
        (aiohttp.ClientConnectionError(), "cannot_connect"),
    ],
)
async def test_reconfigure_fail_with_error(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_config_entry: MockConfigEntry,
    mock_discover_devices: AsyncMock,
    exception: Exception,
    expected_error: str,
) -> None:
    """Test reconfigure flow with an error."""
    url = "http://10.0.0.100"

    mock_lunatone_info.async_update.side_effect = exception

    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "url_input"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: url}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": expected_error}

    mock_lunatone_info.async_update.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_URL: url}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {CONF_URL: url}
