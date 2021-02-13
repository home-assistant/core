"""Test the Transports Metropolitans de Barcelona config flow."""
from homeassistant import config_entries, setup
from homeassistant.components.tmb.const import (
    DOMAIN,
    STEP_FEATURE_IBUS,
    STEP_FEATURE_PLANNER,
    STEP_SELECT,
)
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)

from . import (
    MOCK_CONF,
    USER_INPUT_IBUS,
    USER_INPUT_PLANNER,
    USER_INPUT_SELECT_IBUS,
    USER_INPUT_SELECT_PLANNER,
)


async def test_form_missing_conf(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "missing_configuration"


async def test_form_feature_ibus(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    hass.data[DOMAIN] = MOCK_CONF

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == STEP_SELECT
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT_SELECT_IBUS,
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == STEP_FEATURE_IBUS
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT_IBUS,
    )
    assert result["type"] == RESULT_TYPE_CREATE_ENTRY


async def test_form_feature_planner(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    hass.data[DOMAIN] = MOCK_CONF

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == STEP_SELECT
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT_SELECT_PLANNER,
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == STEP_FEATURE_PLANNER
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT_PLANNER,
    )
    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
