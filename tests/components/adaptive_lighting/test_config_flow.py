"""Test Adaptive Lighting config flow."""
from homeassistant import data_entry_flow
from homeassistant.components.adaptive_lighting.const import (
    CONF_SUNRISE_TIME,
    CONF_SUNSET_TIME,
    DEFAULT_NAME,
    DOMAIN,
    NONE_STR,
    VALIDATION_TUPLES,
)
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_NAME

from tests.common import MockConfigEntry

DEFAULT_DATA = {key: default for key, default, _ in VALIDATION_TUPLES}


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


async def test_incorrect_options(hass):
    """Test updating incorrect options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_NAME,
        data={CONF_NAME: DEFAULT_NAME},
        options={},
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    data = DEFAULT_DATA.copy()
    data[CONF_SUNRISE_TIME] = "yolo"
    data[CONF_SUNSET_TIME] = "yolo"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input=data,
    )


async def test_import_twice(hass):
    """Test importing twice."""
    data = DEFAULT_DATA.copy()
    data[CONF_NAME] = DEFAULT_NAME
    for _ in range(2):
        _ = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": "import"},
            data=data,
        )


async def test_changing_options_when_using_yaml(hass):
    """Test changing options when using YAML."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=DEFAULT_NAME,
        data={CONF_NAME: DEFAULT_NAME},
        source=SOURCE_IMPORT,
        options={},
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={},
    )
