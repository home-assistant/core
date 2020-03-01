"""Test config flow."""

from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_manual_config_set(hass):
    """Test we ignore entry if manual config available."""
    assert await async_setup_component(hass, "shopping_list", {})
    await hass.async_block_till_done()

    result = await hass.config_entries.flow.async_init(
        "shopping_list", context={"source": "user"}
    )
    assert result["type"] == "abort"


async def test_user_single_instance(hass):
    """Test we only allow a single config flow."""
    MockConfigEntry(domain="shopping_list").add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        "shopping_list", context={"source": "user"}
    )
    assert result["type"] == "abort"
    assert result["reason"] == "single_instance_allowed"


async def test_user(hass):
    """Test we can start a config flow."""

    result = await hass.config_entries.flow.async_init(
        "shopping_list", data=None, context={"source": "user"}
    )

    assert result["type"] == "form"
    assert result["step_id"] == "user"


async def test_user_confirm(hass):
    """Test we can finish a config flow."""

    result = await hass.config_entries.flow.async_init(
        "shopping_list", data={}, context={"source": "user"}
    )

    assert result["type"] == "create_entry"
    assert result["result"].data == {}
