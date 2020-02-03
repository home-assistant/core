"""Tests for the local_ip config_flow."""
from homeassistant.components.local_ip import DOMAIN


async def test_config_flow(hass):
    """Test we can finish a config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "form"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {"name": "test"}
    )
    assert result["type"] == "create_entry"

    await hass.async_block_till_done()
    state = hass.states.get("sensor.test")
    assert state
