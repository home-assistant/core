"""Test the TheSilentWave config flow."""

from unittest.mock import AsyncMock, patch

from aiohttp import ClientError

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        "thesilentwave", context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}  # Expect empty dict, not None

    with patch(
        "homeassistant.components.thesilentwave.config_flow.ClientSession.get"
    ) as mock_get:
        mock_get.return_value.__aenter__.return_value.status = 200
        mock_get.return_value.__aenter__.return_value.raise_for_status = lambda: None
        mock_get.return_value.__aenter__.return_value.text = AsyncMock(return_value="1")

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Test Device",
                CONF_HOST: "192.168.1.100",
                CONF_SCAN_INTERVAL: 30,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Test Device"
    assert result2["data"] == {
        CONF_NAME: "Test Device",
        CONF_HOST: "192.168.1.100",
        CONF_SCAN_INTERVAL: 30,
    }


async def test_form_invalid_ip(hass: HomeAssistant) -> None:
    """Test we handle invalid IP address."""
    result = await hass.config_entries.flow.async_init(
        "thesilentwave", context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_NAME: "Test Device",
            CONF_HOST: "invalid_ip",
            CONF_SCAN_INTERVAL: 30,
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"host": "invalid_ip"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        "thesilentwave", context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.thesilentwave.config_flow.ClientSession.get",
        side_effect=ClientError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_NAME: "Test Device",
                CONF_HOST: "192.168.1.100",
                CONF_SCAN_INTERVAL: 30,
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"host": "cannot_connect"}


async def test_form_already_configured(hass: HomeAssistant) -> None:
    """Test we handle duplicate entries."""
    # Create an entry first
    with patch(
        "homeassistant.components.thesilentwave.config_flow.ClientSession.get"
    ) as mock_get:
        mock_get.return_value.__aenter__.return_value.status = 200
        mock_get.return_value.__aenter__.return_value.raise_for_status = lambda: None
        mock_get.return_value.__aenter__.return_value.text = AsyncMock(return_value="1")

        result = await hass.config_entries.flow.async_init(
            "thesilentwave",
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_NAME: "Test Device",
                CONF_HOST: "192.168.1.100",
                CONF_SCAN_INTERVAL: 30,
            },
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY

    # Try to add the same host again
    with patch(
        "homeassistant.components.thesilentwave.config_flow.ClientSession.get"
    ) as mock_get:
        mock_get.return_value.__aenter__.return_value.status = 200
        mock_get.return_value.__aenter__.return_value.raise_for_status = lambda: None
        mock_get.return_value.__aenter__.return_value.text = AsyncMock(return_value="1")

        result = await hass.config_entries.flow.async_init(
            "thesilentwave",
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_NAME: "Another Device",
                CONF_HOST: "192.168.1.100",
                CONF_SCAN_INTERVAL: 15,
            },
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
