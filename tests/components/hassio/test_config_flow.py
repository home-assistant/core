"""Test the Home Assistant Supervisor config flow."""
from unittest.mock import patch

from homeassistant.components.hassio import DOMAIN
from homeassistant.core import HomeAssistant


async def test_config_flow(hass: HomeAssistant) -> None:
    """Test we get the form."""

    with patch(
        "homeassistant.components.hassio.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.hassio.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "system"}
        )
        assert result["type"] == "create_entry"
        assert result["title"] == "Supervisor"
        assert result["data"] == {}
        await hass.async_block_till_done()

    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_multiple_entries(hass: HomeAssistant) -> None:
    """Test creating multiple hassio entries."""
    await test_config_flow(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "system"}
    )
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
