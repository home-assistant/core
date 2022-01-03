"""Test launch_library config flow."""

from homeassistant import data_entry_flow
from homeassistant.components.launch_library.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER

from tests.common import MockConfigEntry


async def test_import(hass):
    """Test entry will be imported."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data={}
    )
    assert result.get("type") == data_entry_flow.RESULT_TYPE_CREATE_ENTRY


async def test_user(hass):
    """Test we can start a config flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") == data_entry_flow.RESULT_TYPE_FORM
    assert result.get("step_id") == "user"


async def test_user_confirm(hass):
    """Test we can finish a config flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data={}
    )

    assert result.get("type") == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result.get("result").data == {}


async def test_user_already_configured(hass):
    """Test we only allow a single config flow."""

    MockConfigEntry(
        domain=DOMAIN,
        data={},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data={}
    )

    assert result.get("type") == data_entry_flow.RESULT_TYPE_ABORT
    assert result.get("reason") == "single_instance_allowed"
