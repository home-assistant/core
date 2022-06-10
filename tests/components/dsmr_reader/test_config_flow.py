"""Tests for the config flow."""
from unittest.mock import MagicMock

from homeassistant.components.dsmr_reader.const import DOMAIN
from homeassistant.components.mqtt import DATA_MQTT
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from tests.common import MockConfigEntry


async def test_import_step(hass: HomeAssistant):
    """Test the import step."""
    # configure bogus mqtt service to pass validation
    hass.services.async_register("mqtt", "publish", None)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
    )
    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "DSMR Reader"

    second_result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
    )
    assert second_result["type"] == RESULT_TYPE_ABORT
    assert second_result["reason"] == "single_instance_allowed"


async def test_initial_user_step(hass: HomeAssistant):
    """Test the initial user step call."""
    init_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert init_result["type"] == RESULT_TYPE_FORM
    assert init_result["step_id"] == "confirm"
    assert {"base": "mqtt_missing"} == init_result["errors"]


async def test_duplicate_user_step(hass: HomeAssistant):
    """Test the user step call when an instance has already been installed."""
    mock = MockConfigEntry(domain="dsmr_reader")
    mock.add_to_hass(hass)
    init_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert init_result["type"] == RESULT_TYPE_ABORT
    assert init_result["reason"] == "single_instance_allowed"


async def test_user_step_with_mqtt(hass: HomeAssistant):
    """Test the user step call with mqtt available."""
    # configure bogus mqtt service to pass validation
    hass.services.async_register("mqtt", "publish", None)
    hass.data[DATA_MQTT] = {"async_subscribe": MagicMock()}

    init_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert init_result["type"] == RESULT_TYPE_FORM
    assert init_result["step_id"] == "confirm"
    assert init_result["errors"] is None

    config_result = await hass.config_entries.flow.async_configure(
        init_result["flow_id"], user_input={}
    )

    assert config_result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert config_result["title"] == "DSMR Reader"
