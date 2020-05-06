"""Tests for Islamic Prayer Times config flow."""
import pytest

from homeassistant import data_entry_flow
from homeassistant.components import islamic_prayer_times
from homeassistant.components.islamic_prayer_times.const import CONF_CALC_METHOD, DOMAIN

from tests.async_mock import patch
from tests.common import MockConfigEntry


@pytest.fixture(name="mock_setup", autouse=True)
def mock_setup():
    """Mock entry setup."""
    with patch(
        "homeassistant.components.islamic_prayer_times.async_setup_entry",
        return_value=True,
    ):
        yield


async def test_flow_works(hass):
    """Test user config."""
    result = await hass.config_entries.flow.async_init(
        islamic_prayer_times.DOMAIN, context={"source": "user"}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Islamic Prayer Times"


async def test_options(hass):
    """Test updating options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Islamic Prayer Times",
        data={},
        options={CONF_CALC_METHOD: "isna"},
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_CALC_METHOD: "makkah"}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"][CONF_CALC_METHOD] == "makkah"


async def test_import(hass):
    """Test import step."""
    result = await hass.config_entries.flow.async_init(
        islamic_prayer_times.DOMAIN,
        context={"source": "import"},
        data={CONF_CALC_METHOD: "makkah"},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "Islamic Prayer Times"
    assert result["data"][CONF_CALC_METHOD] == "makkah"


async def test_integration_already_configured(hass):
    """Test integration is already configured."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={},)
    entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        islamic_prayer_times.DOMAIN, context={"source": "user"}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "one_instance_allowed"
