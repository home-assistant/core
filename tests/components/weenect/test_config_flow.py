"""Test weenect config flow."""
from unittest.mock import patch

import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.weenect.const import DOMAIN

from .const import MOCK_CONFIG

from tests.common import MockConfigEntry


@pytest.fixture(autouse=True)
def bypass_setup_fixture():
    """Prevent setup."""
    with patch(
        "homeassistant.components.weenect.async_setup_entry",
        return_value=True,
    ):
        yield


@pytest.mark.usefixtures("bypass_get_trackers", "bypass_login")
async def test_successful_config_flow(hass):
    """Test a successful config flow."""
    # Initialize a config flow
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_CONFIG
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "test_username"
    assert result["data"] == MOCK_CONFIG
    assert result["result"]


@pytest.mark.usefixtures("bypass_get_trackers", "bypass_login")
async def test_already_configured(hass):
    """Test already configured result."""
    MockConfigEntry(domain=DOMAIN, data=MOCK_CONFIG, entry_id="test").add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, data=MOCK_CONFIG, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") == "abort"
    assert result.get("reason") == "already_configured"


@pytest.mark.usefixtures("error_on_get_trackers")
async def test_failed_config_flow(hass):
    """Test a failed config flow due to credential validation failure."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=MOCK_CONFIG
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"base": "auth"}
