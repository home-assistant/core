"""Test the Z-Wave over MQTT config flow."""
from asynctest import patch

from homeassistant import config_entries, setup
from homeassistant.components.zwave_mqtt.config_flow import TITLE
from homeassistant.components.zwave_mqtt.const import DOMAIN


async def test_user_create_entry(hass):
    """Test the user step creates an entry."""
    hass.config.components.add("mqtt")
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] is None

    with patch(
        "homeassistant.components.zwave_mqtt.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.zwave_mqtt.async_setup_entry", return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result2["type"] == "create_entry"
    assert result2["title"] == TITLE
    assert result2["data"] == {}
    await hass.async_block_till_done()
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
