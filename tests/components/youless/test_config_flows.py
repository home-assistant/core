"""Test the youless config flow."""

from homeassistant import config_entries
from homeassistant.components.youless import DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.data_entry_flow import RESULT_TYPE_FORM

MOCK_CONFIG = {CONF_HOST: "172.0.0.1", CONF_NAME: "Test setup"}


async def test_full_flow(hass, aiohttp_client, aioclient_mock, current_request):
    """Check setup."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["errors"] == {}
    assert result["step_id"] == config_entries.SOURCE_USER
