"""Test config flow."""

from homeassistant.components.shopping_list.const import DOMAIN
from homeassistant.const import CONF_TYPE
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_manual_config_set(hass):
    """Test we ignore entry if manual config available."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result[CONF_TYPE] == "abort"


async def test_user_single_instance(hass):
    """Test we only allow a single config flow."""
    MockConfigEntry(domain=DOMAIN).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result[CONF_TYPE] == "abort"
    assert result["reason"] == "single_instance_allowed"


async def test_user(hass):
    """Test we can start a config flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, data=None, context={"source": "user"}
    )

    assert result[CONF_TYPE] == "form"
    assert result["step_id"] == "user"


async def test_user_confirm(hass):
    """Test we can finish a config flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, data={}, context={"source": "user"}
    )

    assert result[CONF_TYPE] == "create_entry"
    assert result["result"].data == {}
