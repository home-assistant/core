"""Test the switchbot config flow."""

from pygatt.exceptions import NotConnectedError

from homeassistant.components.switchbot.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.data_entry_flow import (
    RESULT_TYPE_ABORT,
    RESULT_TYPE_CREATE_ENTRY,
    RESULT_TYPE_FORM,
)
from homeassistant.setup import async_setup_component

from . import USER_INPUT, YAML_CONFIG, _patch_async_setup_entry


async def test_user_form(hass, switchbot_config_flow):
    """Test the user initiated form with password."""
    await async_setup_component(hass, "persistent_notification", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    with _patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            USER_INPUT,
        )
    await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "test-name"
    assert result["data"] == {
        "mac": "00:00:00",
        "name": "test-name",
        "password": "test-password",
        "sensor_type": "bot",
    }

    assert len(mock_setup_entry.mock_calls) == 1

    # test duplicate device creation fails.

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )
    await hass.async_block_till_done()

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured_device"


async def test_async_step_import(hass):
    """Test the config import flow."""
    await async_setup_component(hass, "persistent_notification", {})

    with _patch_async_setup_entry() as mock_setup_entry:
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=YAML_CONFIG
        )
    assert result["type"] == RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == {
        "mac": "00:00:00",
        "name": "test-name",
        "password": "test-password",
        "sensor_type": "bot",
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_form_exception(hass, switchbot_config_flow):
    """Test we handle exception on user form."""
    await async_setup_component(hass, "persistent_notification", {})

    switchbot_config_flow.side_effect = NotConnectedError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    assert result["type"] == RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}

    switchbot_config_flow.side_effect = Exception

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        USER_INPUT,
    )

    assert result["type"] == RESULT_TYPE_ABORT
    assert result["reason"] == "unknown"
