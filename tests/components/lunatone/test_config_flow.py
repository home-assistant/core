"""Define tests for the Lunatone config flow."""

from unittest.mock import AsyncMock

import aiohttp

from homeassistant.components.lunatone.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_URL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import BASE_URL, SERIAL_NUMBER

from tests.common import MockConfigEntry


async def test_full_flow(
    hass: HomeAssistant, mock_lunatone_info: AsyncMock, mock_setup_entry: AsyncMock
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
        {CONF_URL: BASE_URL},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Test {SERIAL_NUMBER}"
    assert result["data"] == {CONF_URL: BASE_URL}


async def test_full_flow_fail_because_of_missing_device_infos(
    hass: HomeAssistant,
    mock_lunatone_info: AsyncMock,
) -> None:
    """Test full flow."""
    mock_lunatone_info.data = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: BASE_URL},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "missing_device_info"}


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
        user_input={CONF_URL: BASE_URL},
    )

    assert result2.get("type") is FlowResultType.ABORT
    assert result2.get("reason") == "already_configured"


async def test_user_step_invalid_url(
    hass: HomeAssistant, mock_lunatone_info: AsyncMock
) -> None:
    """Test if cannot connect."""
    mock_lunatone_info.async_update.side_effect = aiohttp.InvalidUrlClientError(
        BASE_URL
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: BASE_URL},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_url"}

    mock_lunatone_info.async_update.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: BASE_URL},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == f"Test {SERIAL_NUMBER}"
    assert result["data"] == {CONF_URL: BASE_URL}


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
        {CONF_URL: BASE_URL},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_reconfigure(
    hass: HomeAssistant, mock_lunatone_info: AsyncMock, mock_config_entry: AsyncMock
) -> None:
    """Test reconfigure flow."""
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_URL: "http://10.0.0.100"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == {
        CONF_URL: "http://10.0.0.100",
    }
