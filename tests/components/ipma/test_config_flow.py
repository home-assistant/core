"""Tests for IPMA config flow."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.ipma.const import DOMAIN
from homeassistant.const import CONF_LATITUDE, CONF_LONGITUDE, CONF_NAME
from homeassistant.core import HomeAssistant

from tests.components.ipma import MockLocation


@pytest.fixture(name="ipma_setup", autouse=True)
def ipma_setup_fixture(request):
    """Patch ipma setup entry."""
    with patch("homeassistant.components.ipma.async_setup_entry", return_value=True):
        yield


async def test_config_flow(hass: HomeAssistant) -> None:
    """Test configuration form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"

    test_data = {
        CONF_LONGITUDE: 0,
        CONF_LATITUDE: 0,
    }
    with patch(
        "pyipma.location.Location.get",
        return_value=MockLocation(),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            test_data,
        )

    assert result["type"] is data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["title"] == "HomeTown"
    assert result["data"] == {
        CONF_LONGITUDE: 0,
        CONF_LATITUDE: 0,
    }


async def test_flow_entry_already_exists(hass: HomeAssistant, config_entry) -> None:
    """Test user input for config_entry that already exists.

    Test when the form should show when user puts existing location
    in the config gui. Then the form should show with error.
    """
    test_data = {
        CONF_NAME: "Home",
        CONF_LONGITUDE: 0,
        CONF_LATITUDE: 0,
    }

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}, data=test_data
    )
    await hass.async_block_till_done()

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
