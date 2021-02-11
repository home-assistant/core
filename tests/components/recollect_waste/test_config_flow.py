"""Define tests for the ReCollect Waste config flow."""
from unittest.mock import patch

from aiorecollect.errors import RecollectError

from homeassistant import data_entry_flow
from homeassistant.components.recollect_waste import (
    CONF_PLACE_ID,
    CONF_SERVICE_ID,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_FRIENDLY_NAME

from tests.common import MockConfigEntry


async def test_duplicate_error(hass):
    """Test that errors are shown when duplicates are added."""
    conf = {CONF_PLACE_ID: "12345", CONF_SERVICE_ID: "12345"}

    MockConfigEntry(domain=DOMAIN, unique_id="12345, 12345", data=conf).add_to_hass(
        hass
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=conf
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_invalid_place_or_service_id(hass):
    """Test that an invalid Place or Service ID throws an error."""
    conf = {CONF_PLACE_ID: "12345", CONF_SERVICE_ID: "12345"}

    with patch(
        "aiorecollect.client.Client.async_get_next_pickup_event",
        side_effect=RecollectError,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=conf
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["errors"] == {"base": "invalid_place_or_service_id"}


async def test_options_flow(hass):
    """Test config flow options."""
    conf = {CONF_PLACE_ID: "12345", CONF_SERVICE_ID: "12345"}

    config_entry = MockConfigEntry(domain=DOMAIN, unique_id="12345, 12345", data=conf)
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.recollect_waste.async_setup_entry", return_value=True
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        result = await hass.config_entries.options.async_init(config_entry.entry_id)

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "init"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"], user_input={CONF_FRIENDLY_NAME: True}
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert config_entry.options == {CONF_FRIENDLY_NAME: True}


async def test_show_form(hass):
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"


async def test_step_import(hass):
    """Test that the user step works."""
    conf = {CONF_PLACE_ID: "12345", CONF_SERVICE_ID: "12345"}

    with patch(
        "homeassistant.components.recollect_waste.async_setup_entry", return_value=True
    ), patch(
        "aiorecollect.client.Client.async_get_next_pickup_event", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=conf
        )
        await hass.async_block_till_done()
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "12345, 12345"
        assert result["data"] == {CONF_PLACE_ID: "12345", CONF_SERVICE_ID: "12345"}


async def test_step_user(hass):
    """Test that the user step works."""
    conf = {CONF_PLACE_ID: "12345", CONF_SERVICE_ID: "12345"}

    with patch(
        "homeassistant.components.recollect_waste.async_setup_entry", return_value=True
    ), patch(
        "aiorecollect.client.Client.async_get_next_pickup_event", return_value=True
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=conf
        )
        await hass.async_block_till_done()
        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["title"] == "12345, 12345"
        assert result["data"] == {CONF_PLACE_ID: "12345", CONF_SERVICE_ID: "12345"}
