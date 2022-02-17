"""Tests for the EDL21 config flow."""
import aiohttp

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.edl21.sensor import DOMAIN, CONF_SERIAL_PORT
from homeassistant.components.hassio import HassioServiceInfo
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_show_config_form(hass: HomeAssistant) -> None:
    """Test that the setup form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

async def test_with_data(
    hass: HomeAssistant ) -> None:

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_SERIAL_PORT: "/dev/ttyTEST", CONF_NAME: "TEST"},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY