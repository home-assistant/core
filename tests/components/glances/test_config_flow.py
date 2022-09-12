"""Tests for Glances config flow."""
from unittest.mock import patch

from glances_api import exceptions
import pytest

from homeassistant import config_entries, data_entry_flow
from homeassistant.components import glances
from homeassistant.const import CONF_SCAN_INTERVAL
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

NAME = "Glances"
HOST = "0.0.0.0"
USERNAME = "username"
PASSWORD = "password"
PORT = 61208
VERSION = 3
SCAN_INTERVAL = 10

DEMO_USER_INPUT = {
    "host": HOST,
    "username": USERNAME,
    "password": PASSWORD,
    "version": VERSION,
    "port": PORT,
    "ssl": False,
    "verify_ssl": True,
}


@pytest.fixture(autouse=True)
def glances_setup_fixture():
    """Mock transmission entry setup."""
    with patch("homeassistant.components.glances.async_setup_entry", return_value=True):
        yield


async def test_form(hass: HomeAssistant) -> None:
    """Test config entry configured successfully."""

    result = await hass.config_entries.flow.async_init(
        glances.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch("homeassistant.components.glances.Glances.get_data", autospec=True):

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=DEMO_USER_INPUT
        )

    assert result["type"] == "create_entry"
    assert result["title"] == HOST
    assert result["data"] == DEMO_USER_INPUT


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test to return error if we cannot connect."""

    with patch(
        "homeassistant.components.glances.Glances.get_data",
        side_effect=exceptions.GlancesApiConnectionError,
    ):
        result = await hass.config_entries.flow.async_init(
            glances.DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=DEMO_USER_INPUT
        )

    assert result["type"] == "form"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_form_already_configured(hass: HomeAssistant) -> None:
    """Test host is already configured."""
    entry = MockConfigEntry(
        domain=glances.DOMAIN, data=DEMO_USER_INPUT, options={CONF_SCAN_INTERVAL: 60}
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        glances.DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=DEMO_USER_INPUT
    )
    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_options(hass: HomeAssistant) -> None:
    """Test options for Glances."""
    entry = MockConfigEntry(
        domain=glances.DOMAIN, data=DEMO_USER_INPUT, options={CONF_SCAN_INTERVAL: 60}
    )
    entry.add_to_hass(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == data_entry_flow.FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={glances.CONF_SCAN_INTERVAL: 10}
    )

    assert result["type"] == data_entry_flow.FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        glances.CONF_SCAN_INTERVAL: 10,
    }
