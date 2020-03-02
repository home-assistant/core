"""Test config flow."""

from homeassistant.components.shopping_list.const import DOMAIN
from homeassistant.setup import async_setup_component


async def test_manual_config_set(hass):
    """Test entry will be imported."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        DOMAIN, data={}, context={"source": "user"}
    )
    assert result["type"] == "create_entry"


async def test_user(hass):
    """Test we can start a config flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, data=None, context={"source": "user"}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"


async def test_user_confirm(hass):
    """Test we can finish a config flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, data={}, context={"source": "user"}
    )

    assert result["type"] == "create_entry"
    assert result["result"].data == {}
