"""Test the TheSilentWave config flow."""

from unittest.mock import AsyncMock, patch

from pysilentwave.exceptions import SilentWaveError

from homeassistant import config_entries
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from homeassistant.components.thesilentwave.const import DOMAIN


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}  # Expect empty dict, not None

    with patch(
        "homeassistant.components.thesilentwave.config_flow.SilentWaveClient.get_status",
        new=AsyncMock(return_value={"status": "on"}),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "TheSilentWave"
    assert result2["data"] == {
        CONF_HOST: "192.168.1.100",
    }


async def test_form_invalid_ip(hass: HomeAssistant) -> None:
    """Test we handle invalid IP address."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "invalid_ip",
        },
    )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {CONF_HOST: "invalid_ip"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.thesilentwave.config_flow.SilentWaveClient.get_status",
        side_effect=SilentWaveError("Connection failed"),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "192.168.1.100",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {CONF_HOST: "cannot_connect"}


async def test_form_already_configured(hass: HomeAssistant) -> None:
    """Test we handle duplicate entries."""
    # Create an entry first
    with patch(
        "homeassistant.components.thesilentwave.config_flow.SilentWaveClient.get_status",
        new=AsyncMock(return_value={"status": "on"}),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_HOST: "192.168.1.100",
            },
        )
        assert result["type"] == FlowResultType.CREATE_ENTRY

    # Try to add the same host again
    with patch(
        "homeassistant.components.thesilentwave.config_flow.SilentWaveClient.get_status",
        new=AsyncMock(return_value={"status": "on"}),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data={
                CONF_HOST: "192.168.1.100",
            },
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"
