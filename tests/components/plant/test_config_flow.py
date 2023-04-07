"""Test the plant config flow."""
from homeassistant.components.plant import DOMAIN
from homeassistant.components.plant.const import CONF_PLANT_NAME
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import ATTR_UNIT_OF_MEASUREMENT, CONDUCTIVITY, CONF_SOURCE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    MOCK_USER_INPUT_DYNAMIC_SENSORS,
    MOCK_USER_INPUT_LIMITS,
    MOCK_USER_INPUT_SENSORS,
    MOCK_USER_INPUT_USER,
)


async def test_show_user_form(hass: HomeAssistant) -> None:
    """Test that the user set up form is served."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
    )

    assert result["step_id"] == "user"
    assert result["type"] == FlowResultType.FORM


async def test_show_sensor_form(hass: HomeAssistant) -> None:
    """Test that the sensor form is shown after the name is filled in."""
    user_input = MOCK_USER_INPUT_USER.copy()
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={CONF_SOURCE: SOURCE_USER}, data=user_input
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "sensors"


async def test_show_limits_form(hass: HomeAssistant) -> None:
    """Test that the sensor form is only showing the needed fields."""
    user_inputs = MOCK_USER_INPUT_DYNAMIC_SENSORS.copy()
    for data in user_inputs:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={CONF_SOURCE: "sensors"}, data=data["input"]
        )

        assert result["type"] == FlowResultType.FORM
        assert result["step_id"] == "limits"
        assert len(result["data_schema"].schema.keys() - data["output"]) == 0


async def test_full_user_flow_implementation(hass: HomeAssistant) -> None:
    """Test the full user flow."""
    hass.states.async_set(
        "sensor.mqtt_plant_moisture", 5, {ATTR_UNIT_OF_MEASUREMENT: CONDUCTIVITY}
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_USER},
    )

    assert result["step_id"] == "user"
    assert result["type"] == FlowResultType.FORM

    user_input = MOCK_USER_INPUT_USER.copy()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "sensors"

    user_input = MOCK_USER_INPUT_SENSORS.copy()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "limits"
    assert len(result["data_schema"].schema.keys()) == 10

    user_input = MOCK_USER_INPUT_LIMITS.copy()

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == MOCK_USER_INPUT_USER[CONF_PLANT_NAME]
    assert result["data"]["sensors"] == MOCK_USER_INPUT_SENSORS
