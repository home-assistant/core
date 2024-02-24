"""Test the Home Assistant Cloud config flow."""
from unittest.mock import patch

from homeassistant.components.cloud.const import DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_config_flow(hass: HomeAssistant) -> None:
    """Test create cloud entry."""

    with patch(
        "homeassistant.components.cloud.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.cloud.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "system"}
        )
        assert result["type"] == "create_entry"
        assert result["title"] == "Home Assistant Cloud"
        assert result["data"] == {}
        await hass.async_block_till_done()

    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_multiple_entries(hass: HomeAssistant) -> None:
    """Test creating multiple cloud entries."""
    config_entry = MockConfigEntry(domain=DOMAIN)
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "system"}
    )
    assert result["type"] == "abort"
    assert result["reason"] == "single_instance_allowed"
