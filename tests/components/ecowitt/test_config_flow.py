"""Test the Ecowitt Weather Station config flow."""
from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.components.ecowitt.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_create_entry(hass: HomeAssistant) -> None:
    """Test we can create a config entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.ecowitt.config_flow.EcoWittListener.start",
        AsyncMock(),
    ), patch(
        "homeassistant.components.ecowitt.config_flow.EcoWittListener.stop", AsyncMock()
    ), patch(
        "homeassistant.components.ecowitt.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "port": 49911,
                "path": "/ecowitt-station",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Ecowitt on port 49911"
    assert result2["data"] == {
        "port": 49911,
        "path": "/ecowitt-station",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_port(hass: HomeAssistant) -> None:
    """Test we handle invalid port."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.ecowitt.config_flow.EcoWittListener.start",
        AsyncMock(side_effect=OSError),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "port": 49911,
                "path": "/ecowitt-station",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_port"}


async def test_already_configured_port(hass: HomeAssistant) -> None:
    """Test already configured port."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] is None

    with patch(
        "homeassistant.components.ecowitt.config_flow.EcoWittListener.start",
        AsyncMock(),
    ), patch(
        "homeassistant.components.ecowitt.config_flow.EcoWittListener.stop", AsyncMock()
    ), patch(
        "homeassistant.components.ecowitt.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "port": 49911,
                "path": "/ecowitt-station",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert len(mock_setup_entry.mock_calls) == 1

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.ecowitt.config_flow.EcoWittListener.start",
        AsyncMock(side_effect=OSError),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "port": 49911,
                "path": "/ecowitt-station",
            },
        )

    assert result3["type"] == FlowResultType.FORM
    assert result3["errors"] == {"base": "invalid_port"}


async def test_unknown_error(hass: HomeAssistant) -> None:
    """Test we handle unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.ecowitt.config_flow.EcoWittListener.start",
        side_effect=Exception()),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "port": 49911,
                "path": "/ecowitt-station",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}
