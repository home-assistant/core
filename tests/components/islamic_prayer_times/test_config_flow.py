"""Tests for Islamic Prayer Times config flow."""
from tests.common import MockConfigEntry

from homeassistant.components.islamic_prayer_times import config_flow
from homeassistant.components.islamic_prayer_times.const import CONF_CALC_METHOD, DOMAIN


async def test_flow_works(hass):
    """Test user config."""
    flow = config_flow.IslamicPrayerFlowHandler()
    flow.hass = hass

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )
    assert result["type"] == "form", result

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] == "create_entry"
    assert result["title"] == "Islamic Prayer Times"


async def test_options(hass):
    """Test updating options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Islamic Prayer Times",
        data={},
        options={CONF_CALC_METHOD: "isna"},
    )
    flow = config_flow.IslamicPrayerFlowHandler()
    flow.hass = hass
    options_flow = flow.async_get_options_flow(entry)

    result = await options_flow.async_step_init()
    assert result["type"] == "form"
    assert result["step_id"] == "init"

    result = await options_flow.async_step_init({CONF_CALC_METHOD: "makkah"})
    assert result["type"] == "create_entry"
    assert result["data"][CONF_CALC_METHOD] == "makkah"

    # Test calc_method is wrong

    result = await options_flow.async_step_init({CONF_CALC_METHOD: "bla"})

    assert result["type"] == "form"
    assert result["errors"] == {CONF_CALC_METHOD: "wrong_method"}


async def test_import(hass):
    """Test import step."""
    flow = config_flow.IslamicPrayerFlowHandler()
    flow.hass = hass

    result = await flow.async_step_import({CONF_CALC_METHOD: "makkah"})
    assert result["type"] == "create_entry"
    assert result["title"] == "Islamic Prayer Times"
    assert result["data"][CONF_CALC_METHOD] == "makkah"


async def test_integration_already_configured(hass):
    """Test integration is already configured."""
    entry = MockConfigEntry(domain=DOMAIN, data={}, options={},)
    entry.add_to_hass(hass)
    flow = config_flow.IslamicPrayerFlowHandler()
    flow.hass = hass
    result = await flow.async_step_user()

    assert result["type"] == "abort"
    assert result["reason"] == "one_instance_allowed"
