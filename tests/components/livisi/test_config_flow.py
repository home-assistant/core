"""Test the Livisi Home Assistant config flow."""

import pytest

from homeassistant import data_entry_flow
from homeassistant.components.livisi.const import CONF_HOST, CONF_PASSWORD, DOMAIN
from homeassistant.config_entries import SOURCE_USER

from tests.common import MockConfigEntry


@pytest.fixture(name="config")
def config_fixture(hass):
    """Define a config entry data fixture."""
    return {
        CONF_HOST: "1.1.1.1",
        CONF_PASSWORD: "test",
    }


@pytest.fixture(name="config_entry")
def config_entry_fixture(hass, config):
    """Define a config entry fixture."""
    entry = MockConfigEntry(domain=DOMAIN, data=config)
    entry.add_to_hass(hass)
    return entry


async def test_show_form(hass):
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_step_user(hass, config):
    """Test that the user step works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=config
    )

    assert result["type"] == data_entry_flow.FlowResultType.FORM
