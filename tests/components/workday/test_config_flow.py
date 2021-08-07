"""Test the Workday config flow."""
import logging

from homeassistant import config_entries
from homeassistant.components.workday.const import (
    CONF_ADD_HOLIDAYS,
    CONF_COUNTRY,
    CONF_EXCLUDES,
    CONF_OFFSET,
    CONF_PROVINCE,
    CONF_REMOVE_HOLIDAYS,
    CONF_STATE,
    CONF_SUBCOUNTRY,
    CONF_WORKDAYS,
    DEFAULT_EXCLUDES,
    DEFAULT_OFFSET,
    DEFAULT_WORKDAYS,
    DOMAIN,
    ERR_NO_SUBCOUNTRY,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant

from tests.components.workday import (
    create_flow_advanced_data,
    create_flow_basic_data,
    create_workday_test_data,
)

_LOGGER = logging.getLogger(__name__)

FLOW_BASIC_01 = create_flow_basic_data(country="Germany", subcountry="BW")
FLOW_BASIC_02 = create_flow_basic_data(country="UnitedStates", subcountry="AL")
FLOW_BASIC_03 = create_flow_basic_data(country="Ukraine")
FLOW_ADVANCED_INIT = create_flow_basic_data(
    country="Germany", subcountry="BW", advanced_config=True
)
FLOW_ADVANCED_01 = create_flow_advanced_data(
    workdays=["tue", "wed", "thu", "fri"], excludes=["sat", "holiday"]
)

CONFIG_BASIC_01 = create_workday_test_data(country="Germany", province="BW")
CONFIG_BASIC_02 = create_workday_test_data(country="UnitedStates", state="AL")
CONFIG_BASIC_03 = create_workday_test_data(country="Ukraine")
CONFIG_ADVANCED_01 = create_workday_test_data(
    country="Germany",
    province="BW",
    advanced_config=True,
    workdays=["tue", "wed", "thu", "fri"],
    excludes=["sat", "holiday"],
)


async def test_basic_flow_province(hass: HomeAssistant):
    """Test flow setup."""
    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result1["type"] == "form"
    assert result1["step_id"] == "user"
    assert not result1["errors"]

    result2 = await hass.config_entries.flow.async_configure(
        result1["flow_id"], FLOW_BASIC_01
    )
    await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Workday Germany (BW)"
    assert result2["data"] == CONFIG_BASIC_01


async def test_basic_flow_state(hass: HomeAssistant):
    """Test flow setup."""
    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result1["type"] == "form"
    assert result1["step_id"] == "user"
    assert not result1["errors"]

    result2 = await hass.config_entries.flow.async_configure(
        result1["flow_id"], FLOW_BASIC_02
    )
    await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Workday UnitedStates (AL)"
    assert result2["data"] == CONFIG_BASIC_02


async def test_basic_flow(hass: HomeAssistant):
    """Test flow setup."""
    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result1["type"] == "form"
    assert result1["step_id"] == "user"
    assert not result1["errors"]

    result2 = await hass.config_entries.flow.async_configure(
        result1["flow_id"], FLOW_BASIC_03
    )
    await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Workday Ukraine"
    assert result2["data"] == CONFIG_BASIC_03


async def test_advanced_flow(hass: HomeAssistant):
    """Test flow setup."""
    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result1["type"] == "form"
    assert result1["step_id"] == "user"
    assert not result1["errors"]

    result2 = await hass.config_entries.flow.async_configure(
        result1["flow_id"], FLOW_ADVANCED_INIT
    )
    await hass.async_block_till_done()

    assert result2["type"] == "form"
    assert result2["step_id"] == "advanced_conf"
    assert not result2["errors"]

    result3 = await hass.config_entries.flow.async_configure(
        result2["flow_id"], FLOW_ADVANCED_01
    )
    await hass.async_block_till_done()

    assert result3["type"] == "create_entry"
    assert result3["title"] == "Workday Germany (BW)"
    assert result3["data"] == CONFIG_ADVANCED_01


async def test_import(hass: HomeAssistant):
    """Test import from yaml."""
    mock_import = {
        CONF_COUNTRY: "Germany",
        CONF_PROVINCE: "BW",
        CONF_ADD_HOLIDAYS: [
            "2020-06-01",
            "2020-12-07",
            "2021-02-15",
            "2021-05-24",
        ],
        CONF_REMOVE_HOLIDAYS: [
            "2021-01-01",
        ],
    }

    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=mock_import
    )
    await hass.async_block_till_done()

    assert result1["type"] == "form"
    assert result1["step_id"] == "import_confirm"
    _LOGGER.debug("result1: %s", result1)

    result2 = await hass.config_entries.flow.async_configure(
        result1["flow_id"], user_input={}
    )

    assert result2["type"] == "create_entry"
    assert result2["title"] == "Workday Germany (BW)"
    assert len(result2["data"].get(CONF_ADD_HOLIDAYS)) == 4
    assert len(result2["data"].get(CONF_REMOVE_HOLIDAYS)) == 1

    assert result2["data"] == {
        CONF_COUNTRY: "Germany",
        CONF_SUBCOUNTRY: "BW",
        CONF_WORKDAYS: DEFAULT_WORKDAYS,
        CONF_EXCLUDES: DEFAULT_EXCLUDES,
        CONF_OFFSET: DEFAULT_OFFSET,
        CONF_NAME: "Workday Germany (BW)",
        CONF_PROVINCE: "BW",
        CONF_STATE: None,
        CONF_ADD_HOLIDAYS: [
            "2020-06-01",
            "2020-12-07",
            "2021-02-15",
            "2021-05-24",
        ],
        CONF_REMOVE_HOLIDAYS: [
            "2021-01-01",
        ],
    }

    await hass.async_block_till_done()

    # Duplicate
    result3 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_IMPORT}, data=mock_import
    )
    assert result3["type"] == "abort"
    assert result3["reason"] == "already_configured"


async def test_import_fail(hass: HomeAssistant):
    """Test import from yaml."""
    result1 = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_IMPORT},
        data={CONF_COUNTRY: "HomeassistantLand"},
    )
    await hass.async_block_till_done()

    assert result1["type"] == "abort"
    assert result1["reason"] == "config_cannot_be_imported"


async def test_basic_flow_fail(hass: HomeAssistant):
    """Test flow setup."""
    result1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result1["type"] == "form"
    assert result1["step_id"] == "user"
    assert not result1["errors"]

    result2 = await hass.config_entries.flow.async_configure(
        result1["flow_id"],
        user_input={
            CONF_COUNTRY: "Germany",
            CONF_SUBCOUNTRY: "no_province",
        },
    )
    await hass.async_block_till_done()

    assert result2["type"] == "form"
    assert result2["step_id"] == "user"
    assert result2["errors"] == {CONF_SUBCOUNTRY: ERR_NO_SUBCOUNTRY}
