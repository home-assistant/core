"""Tests for the config flow."""
from homeassistant.components.dsmr_reader.const import DOMAIN
from homeassistant.config_entries import SOURCE_MQTT, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_CREATE_ENTRY, RESULT_TYPE_FORM
from tests.common import MockConfigEntry


async def test_initial_user_step(hass: HomeAssistant):
    """Test the initial user step call."""
    init_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert init_result["type"] == RESULT_TYPE_FORM
    assert init_result["step_id"] == SOURCE_USER
    assert {"base": "mqtt_missing"} == init_result["errors"]


async def test_user_step_with_mqtt(hass: HomeAssistant):
    """Test the user step call with mqtt available."""
    # configure bogus mqtt service to pass validation
    hass.services.async_register("mqtt", "publish", lambda: {})
    init_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert init_result["type"] == RESULT_TYPE_FORM
    assert init_result["step_id"] == SOURCE_USER
    assert init_result["errors"] is None

    config_result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"], user_input={}
    )

    assert config_result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert config_result["title"] == "DSMR Reader"


async def test_mqtt_step(hass: HomeAssistant):
    """Test the MQTT discovery step preventing duplicate entries"""
    MockConfigEntry(domain="dsmr_reader").add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        "dsmr_reader", context={"source": SOURCE_MQTT}
    )

    assert result["type"] == "abort"
    assert result["reason"] == "single_instance_allowed"
