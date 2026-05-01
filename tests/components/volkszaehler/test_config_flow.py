"""Test config flow for Volkszaehler integration."""

from unittest.mock import AsyncMock, patch

import pytest
from volkszaehler.exceptions import (
    VolkszaehlerApiConnectionError,
    VolkszaehlerNoDataAvailable,
)

from homeassistant.components.volkszaehler import sensor
from homeassistant.components.volkszaehler.const import DOMAIN
from homeassistant.const import (
    CONF_HOST,
    CONF_NAME,
    CONF_PLATFORM,
    CONF_PORT,
    CONF_UUID,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_show_form(hass: HomeAssistant) -> None:
    """Test that the config flow shows the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_create_entry(hass: HomeAssistant) -> None:
    """Test that the config flow creates an entry."""
    user_input = {
        CONF_UUID: "test-uuid",
        CONF_HOST: "localhost",
        CONF_PORT: 80,
    }
    with patch("volkszaehler.Volkszaehler.get_data", new_callable=AsyncMock):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=user_input
        )
        if result["type"] == FlowResultType.FORM:
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input
            )
        assert result["type"] == FlowResultType.CREATE_ENTRY
        assert result["title"] == "test-uuid"
        assert result["data"] == user_input


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (VolkszaehlerApiConnectionError, "cannot_connect"),
        (VolkszaehlerNoDataAvailable, "no_data"),
        (Exception, "unknown"),
    ],
)
async def test_user_errors(
    hass: HomeAssistant, side_effect: type[Exception], expected_error: str
) -> None:
    """Test error handling in the config flow user step."""
    user_input = {
        CONF_UUID: "test-uuid",
        CONF_HOST: "localhost",
        CONF_PORT: 80,
    }
    with patch("volkszaehler.Volkszaehler.get_data", side_effect=side_effect):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": "user"}, data=user_input
        )
        if result["type"] == FlowResultType.FORM:
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input
            )
        assert result["type"] == FlowResultType.FORM
        assert result["errors"]["base"] == expected_error


async def test_import(hass: HomeAssistant) -> None:
    """Test that we can import a config entry."""
    import_data = {
        CONF_UUID: "import-uuid",
        CONF_HOST: "importhost",
        CONF_NAME: "2.8.0",
        CONF_PLATFORM: "volkszaehler",
    }
    with patch("volkszaehler.Volkszaehler.get_data", new_callable=AsyncMock):

        async def dummy_add_entities():
            pass

        await sensor.async_setup_platform(hass, import_data, dummy_add_entities)

        await hass.async_block_till_done()

        entries = hass.config_entries.async_entries(DOMAIN)
        assert len(entries) == 1
        entry = entries[0]
        assert entry.data == {
            CONF_UUID: "import-uuid",
            CONF_HOST: "importhost",
            CONF_PORT: 80,
        }
        assert entry.title == "2.8.0"


async def test_import_once(hass: HomeAssistant) -> None:
    """Test that we import a config entry only once."""
    import_data = {
        CONF_UUID: "import-uuid",
        CONF_HOST: "importhost",
        CONF_PORT: 8080,
        CONF_PLATFORM: "volkszaehler",
    }
    with patch("volkszaehler.Volkszaehler.get_data", new_callable=AsyncMock):

        async def dummy_add_entities():
            pass

        await sensor.async_setup_platform(hass, import_data, dummy_add_entities)
        await sensor.async_setup_platform(hass, import_data, dummy_add_entities)

        await hass.async_block_till_done()

        entries = hass.config_entries.async_entries(DOMAIN)
        assert len(entries) == 1
