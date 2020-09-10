"""Test the Omnilogic config flow."""
from omnilogic import LoginException

from homeassistant import config_entries, setup
from homeassistant.components.omnilogic import config_flow
from homeassistant.components.omnilogic.const import DOMAIN

from tests.async_mock import patch
from tests.common import MockConfigEntry

DATA = {"username": "test-username", "password": "test-password", "polling_interval": 6}


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.omnilogic.config_flow.OmniLogic.connect",
        return_value=True,
    ), patch(
        "homeassistant.components.omnilogic.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.omnilogic.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            DATA,
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Omnilogic"
    assert result2["data"] == DATA
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_already_configured(hass):
    """Test config flow when Omnilogic component is already setup."""
    MockConfigEntry(domain="omnilogic", data=DATA).add_to_hass(hass)

    flow = config_flow.ConfigFlow()
    flow.hass = hass
    flow.context = {}

    fname = "async_step_user"
    func = getattr(flow, fname)
    result = await func(DATA)

    assert result["type"] == "abort"


async def test_without_config(hass):
    """Test config flow with no or incomplete configuration."""

    flow = config_flow.ConfigFlow()
    flow.hass = hass
    flow.context = {}

    fname = "async_step_user"
    func = getattr(flow, fname)
    result = await func()

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.omnilogic.config_flow.OmniLogic.connect",
        return_value=True,
    ), patch(
        "homeassistant.components.omnilogic.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.omnilogic.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"username": "test-username", "password": "test-password"},
        )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Omnilogic"
    assert result2["data"] == DATA
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_with_invalid_credentials(hass):
    """Test with invalid credentials."""

    flow = config_flow.ConfigFlow()
    flow.hass = hass
    flow.context = {}

    fname = "async_step_user"
    func = getattr(flow, fname)
    with patch("omnilogic.OmniLogic.connect", side_effect=LoginException):
        result = await func(DATA)

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}
