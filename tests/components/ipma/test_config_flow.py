"""Tests for IPMA config flow."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.ipma.const import DOMAIN
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant


@pytest.fixture(name="ipma_setup", autouse=True)
def ipma_setup_fixture(request):
    """Patch ipma setup entry."""
    if "disable_autouse_fixture" in request.keywords:
        yield
    else:
        with patch(
            "homeassistant.components.ipma.async_setup_entry", return_value=True
        ):
            yield


async def test_show_config_form(hass: HomeAssistant) -> None:
    """Test show configuration form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"


async def test_flow_entry_already_exists(hass: HomeAssistant) -> None:
    """Test user input for config_entry that already exists.

    Test when the form should show when user puts existing location
    in the config gui. Then the form should show with error.
    """
    test_data = {
        CONF_NAME: "home",
        CONF_LONGITUDE: 0,
        CONF_LATITUDE: 0,
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=test_data
    )
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=test_data
    )
    await hass.async_block_till_done()

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
