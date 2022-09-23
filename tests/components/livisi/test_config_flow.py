"""Test the Livisi Home Assistant config flow."""

from unittest.mock import patch

from aiolivisi import errors as livisi_errors
import pytest

from homeassistant import data_entry_flow
from homeassistant.components.livisi.const import CONF_HOST, CONF_PASSWORD, DOMAIN
from homeassistant.config_entries import SOURCE_USER

from tests.common import MockConfigEntry

VALID_CONFIG = {
    CONF_HOST: "1.1.1.1",
    CONF_PASSWORD: "test",
}


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
    assert result["step_id"] == "credentials"


async def test_api_error(hass):
    """Test API error."""
    with patch(
        "homeassistant.components.livisi.config_flow",
        side_effect=livisi_errors.ShcUnreachableException(),
    ):

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
        )

        assert result["type"] == data_entry_flow.FlowResultType.ABORT
        assert result["reason"] == "shc_unreachable"


async def test_integration_already_exists(hass):
    """Test we only allow a single config flow."""
    MockConfigEntry(
        domain=DOMAIN,
        unique_id="123456",
        data=VALID_CONFIG,
    ).add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data=VALID_CONFIG,
    )

    assert result["type"] == data_entry_flow.FlowResultType.ABORT
    assert result["reason"] == "already_configured"
