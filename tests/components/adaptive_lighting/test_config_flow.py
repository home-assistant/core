"""Test Axis config flow."""
from homeassistant import data_entry_flow
from homeassistant.components.adaptive_lighting.const import (
    CONF_ADAPT_BRIGHTNESS,
    CONF_ADAPT_COLOR_TEMP,
    CONF_ADAPT_RGB_COLOR,
    CONF_DETECT_NON_HA_CHANGES,
    CONF_INITIAL_TRANSITION,
    CONF_INTERVAL,
    CONF_LIGHTS,
    CONF_MAX_BRIGHTNESS,
    CONF_MAX_COLOR_TEMP,
    CONF_MIN_BRIGHTNESS,
    CONF_MIN_COLOR_TEMP,
    CONF_ONLY_ONCE,
    CONF_PREFER_RGB_COLOR,
    CONF_SLEEP_BRIGHTNESS,
    CONF_SLEEP_COLOR_TEMP,
    CONF_SUNRISE_OFFSET,
    CONF_SUNRISE_TIME,
    CONF_SUNSET_OFFSET,
    CONF_SUNSET_TIME,
    CONF_TAKE_OVER_CONTROL,
    CONF_TRANSITION,
    DEFAULT_ADAPT_BRIGHTNESS,
    DEFAULT_ADAPT_COLOR_TEMP,
    DEFAULT_ADAPT_RGB_COLOR,
    DEFAULT_DETECT_NON_HA_CHANGES,
    DEFAULT_INITIAL_TRANSITION,
    DEFAULT_INTERVAL,
    DEFAULT_LIGHTS,
    DEFAULT_MAX_BRIGHTNESS,
    DEFAULT_MAX_COLOR_TEMP,
    DEFAULT_MIN_BRIGHTNESS,
    DEFAULT_MIN_COLOR_TEMP,
    DEFAULT_NAME,
    DEFAULT_ONLY_ONCE,
    DEFAULT_PREFER_RGB_COLOR,
    DEFAULT_SLEEP_BRIGHTNESS,
    DEFAULT_SLEEP_COLOR_TEMP,
    DEFAULT_SUNRISE_OFFSET,
    DEFAULT_SUNSET_OFFSET,
    DEFAULT_TAKE_OVER_CONTROL,
    DEFAULT_TRANSITION,
    DOMAIN,
    NONE_STR,
)
from homeassistant.const import CONF_NAME

from tests.common import MockConfigEntry

DEFAULT_DATA = {
    CONF_LIGHTS: DEFAULT_LIGHTS,
    CONF_ADAPT_BRIGHTNESS: DEFAULT_ADAPT_BRIGHTNESS,
    CONF_ADAPT_COLOR_TEMP: DEFAULT_ADAPT_COLOR_TEMP,
    CONF_ADAPT_RGB_COLOR: DEFAULT_ADAPT_RGB_COLOR,
    CONF_DETECT_NON_HA_CHANGES: DEFAULT_DETECT_NON_HA_CHANGES,
    CONF_INITIAL_TRANSITION: DEFAULT_INITIAL_TRANSITION,
    CONF_INTERVAL: DEFAULT_INTERVAL,
    CONF_MAX_BRIGHTNESS: DEFAULT_MAX_BRIGHTNESS,
    CONF_MAX_COLOR_TEMP: DEFAULT_MAX_COLOR_TEMP,
    CONF_MIN_BRIGHTNESS: DEFAULT_MIN_BRIGHTNESS,
    CONF_MIN_COLOR_TEMP: DEFAULT_MIN_COLOR_TEMP,
    CONF_ONLY_ONCE: DEFAULT_ONLY_ONCE,
    CONF_PREFER_RGB_COLOR: DEFAULT_PREFER_RGB_COLOR,
    CONF_SLEEP_BRIGHTNESS: DEFAULT_SLEEP_BRIGHTNESS,
    CONF_SLEEP_COLOR_TEMP: DEFAULT_SLEEP_COLOR_TEMP,
    CONF_SUNRISE_OFFSET: DEFAULT_SUNRISE_OFFSET,
    CONF_SUNRISE_TIME: None,
    CONF_SUNSET_OFFSET: DEFAULT_SUNSET_OFFSET,
    CONF_SUNSET_TIME: None,
    CONF_TAKE_OVER_CONTROL: DEFAULT_TAKE_OVER_CONTROL,
    CONF_TRANSITION: DEFAULT_TRANSITION,
}


async def test_flow_manual_configuration(hass):
    """Test that config flow works."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "user"}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"
    assert result["handler"] == "adaptive_lighting"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_NAME: "living room"}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "living room"


async def test_import_success(hass):
    """Test import step is successful."""
    data = DEFAULT_DATA.copy()
    data[CONF_NAME] = DEFAULT_NAME
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "import"},
        data=data,
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == DEFAULT_NAME
    for key, value in data.items():
        assert result["data"][key] == value


async def test_options(hass):
    """Test updating options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_NAME,
        data={CONF_NAME: DEFAULT_NAME},
        options={},
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    data = DEFAULT_DATA.copy()
    data[CONF_SUNRISE_TIME] = NONE_STR
    data[CONF_SUNSET_TIME] = NONE_STR
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=data,
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    for key, value in data.items():
        assert result["data"][key] == value
