"""Test iss config flow."""
from unittest.mock import patch

from homeassistant import data_entry_flow
from homeassistant.components.iss.binary_sensor import DEFAULT_NAME
from homeassistant.components.iss.const import DOMAIN
from homeassistant.config import async_process_ha_core_config
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import CONF_NAME, CONF_SHOW_ON_MAP

from tests.common import MockConfigEntry


async def test_import(hass):
    """Test entry will be imported."""

    imported_config = {CONF_NAME: DEFAULT_NAME, CONF_SHOW_ON_MAP: False}

    with patch("homeassistant.components.iss.async_setup_entry", return_value=True):

        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_IMPORT}, data=imported_config
        )
        assert result.get("type") == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result.get("result").data == imported_config


async def test_create_entry(hass):
    """Test we can finish a config flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") == data_entry_flow.RESULT_TYPE_FORM
    assert result.get("step_id") == SOURCE_USER

    with patch("homeassistant.components.iss.async_setup_entry", return_value=True):

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_SHOW_ON_MAP: True},
        )

        assert result.get("type") == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result.get("result").data[CONF_SHOW_ON_MAP] is True


async def test_integration_already_exists(hass):
    """Test we only allow a single config flow."""

    MockConfigEntry(
        domain=DOMAIN,
        data={},
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data={CONF_SHOW_ON_MAP: False}
    )

    assert result.get("type") == data_entry_flow.RESULT_TYPE_ABORT
    assert result.get("reason") == "single_instance_allowed"


async def test_abort_no_home(hass):
    """Test we don't create an entry if no coordinates are set."""

    await async_process_ha_core_config(
        hass,
        {"latitude": 0.0, "longitude": 0.0},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data={CONF_SHOW_ON_MAP: False}
    )

    assert result.get("type") == data_entry_flow.RESULT_TYPE_ABORT
    assert result.get("reason") == "latitude_longitude_not_defined"
