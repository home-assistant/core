"""Define tests for the Lunatone config flow."""

from collections.abc import Generator
from unittest.mock import AsyncMock, PropertyMock, patch

import aiohttp
import pytest

from homeassistant.components.lunatone.config_flow import (
    CONF_SCAN_METHOD,
    DALIDeviceScanMethod,
)
from homeassistant.components.lunatone.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


@pytest.fixture
def mock_lunatone_scan(mock_lunatone_auth: AsyncMock) -> Generator[AsyncMock]:
    """Mock a Lunatone scan object."""
    with patch(
        "homeassistant.components.lunatone.config_flow.DALIScan", autospec=True
    ) as mock_scan:
        scan = mock_scan.return_value
        scan._auth = mock_lunatone_auth
        scan.is_busy = False
        yield scan


async def test_full_flow_no_scan(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test full flow without DALI device scan."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "http://10.0.0.131"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "dali"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_SCAN_METHOD: DALIDeviceScanMethod.DO_NOTHING},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test 12345"
    assert result["data"] == {CONF_URL: "http://10.0.0.131"}


@pytest.mark.parametrize(
    "scan_method",
    [
        DALIDeviceScanMethod.CURRENT_DEVICE_LIST,
        DALIDeviceScanMethod.SYSTEM_EXTENSION,
        DALIDeviceScanMethod.NEW_INSTALLATION,
    ],
)
async def test_full_flow_with_scan(
    hass: HomeAssistant,
    scan_method: DALIDeviceScanMethod,
    mock_lunatone_info: AsyncMock,
    mock_lunatone_scan: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test full flow with all DALI device scan methods."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "http://10.0.0.131"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "dali"

    with patch("homeassistant.components.lunatone.config_flow.asyncio.sleep"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SCAN_METHOD: scan_method},
        )
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "dali"

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "finish"

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Test 12345"
    assert result["data"] == {CONF_URL: "http://10.0.0.131"}


@pytest.mark.parametrize(
    "scan_method",
    [
        DALIDeviceScanMethod.CURRENT_DEVICE_LIST,
        DALIDeviceScanMethod.SYSTEM_EXTENSION,
        DALIDeviceScanMethod.NEW_INSTALLATION,
    ],
)
async def test_full_flow_fail_on_timeout_before_starting_dali_device_scan(
    hass: HomeAssistant,
    scan_method: DALIDeviceScanMethod,
    mock_lunatone_info: AsyncMock,
    mock_lunatone_scan: AsyncMock,
) -> None:
    """Test full flow."""
    mock_lunatone_scan.is_busy = True

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "http://10.0.0.131"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "dali"

    with patch("homeassistant.components.lunatone.config_flow.asyncio.sleep"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_SCAN_METHOD: scan_method}
        )
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "dali"

        mock_lunatone_scan.async_cancel.assert_called_once()
        mock_lunatone_scan.async_update.assert_called()
        assert mock_lunatone_scan.async_update.call_count == 360

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "dali_device_scan_timeout"


@pytest.mark.parametrize(
    "scan_method",
    [
        DALIDeviceScanMethod.CURRENT_DEVICE_LIST,
        DALIDeviceScanMethod.SYSTEM_EXTENSION,
        DALIDeviceScanMethod.NEW_INSTALLATION,
    ],
)
async def test_full_flow_fail_on_timeout_after_starting_dali_device_scan(
    hass: HomeAssistant,
    scan_method: DALIDeviceScanMethod,
    mock_lunatone_info: AsyncMock,
    mock_lunatone_scan: AsyncMock,
) -> None:
    """Test full flow."""
    type(mock_lunatone_scan).is_busy = PropertyMock(side_effect=[False] + [True] * 360)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "http://10.0.0.131"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "dali"

    with patch("homeassistant.components.lunatone.config_flow.asyncio.sleep"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input={CONF_SCAN_METHOD: scan_method}
        )
        assert result["type"] is FlowResultType.SHOW_PROGRESS
        assert result["step_id"] == "dali"

        mock_lunatone_scan.async_cancel.assert_called_once()
        mock_lunatone_scan.async_update.assert_called()
        assert mock_lunatone_scan.async_update.call_count == 361

    result = await hass.config_entries.flow.async_configure(result["flow_id"])
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "dali_device_scan_timeout"


async def test_device_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test that errors are shown when duplicates are added."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_URL: "http://10.0.0.131"},
    )

    assert result2.get("type") is FlowResultType.ABORT
    assert result2.get("reason") == "already_configured"


async def test_user_step_invalid_url(
    hass: HomeAssistant, mock_lunatone_auth: AsyncMock, mock_lunatone_info: AsyncMock
) -> None:
    """Test if cannot connect."""
    mock_lunatone_info.async_update.side_effect = aiohttp.InvalidUrlClientError(
        mock_lunatone_auth.base_url
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "http://10.0.0.131"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_url"}


async def test_user_step_cannot_connect(
    hass: HomeAssistant, mock_lunatone_info: AsyncMock
) -> None:
    """Test if cannot connect."""
    mock_lunatone_info.async_update.side_effect = aiohttp.ClientConnectionError()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "http://10.0.0.131"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_reconfigure(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
    mock_config_entry: AsyncMock,
) -> None:
    """Test reconfigure flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "http://10.0.0.100"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {
        CONF_URL: "http://10.0.0.100",
    }
