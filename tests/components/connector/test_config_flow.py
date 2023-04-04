"""Test the Motion Blinds config flow."""

from homeassistant import config_entries
from homeassistant.components.connector.const import DEFAULT_HUB_NAME, DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_HOST

TEST_HOST = "192.168.31.100&192.168.31.101"
TEST_API_KEY = "12ab345c-d67e-8f"


async def test_config_flow_manual_host_success(hass):
    """Successful flow manually initialized by the user."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"
    assert result["errors"] == {}
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: TEST_HOST, CONF_API_KEY: TEST_API_KEY},
    )

    assert result["type"] == "create_entry"
    assert result["title"] == DEFAULT_HUB_NAME
    assert result["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_API_KEY: TEST_API_KEY,
    }
