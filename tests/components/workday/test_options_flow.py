"""Test the Workday config flow."""
import logging

from homeassistant.components.workday import DOMAIN
from homeassistant.components.workday.config_flow import (
    ACTION_ADD_HOLIDAYS,
    ACTION_REMOVE_HOLIDAYS,
    CONF_HOLIDAY_TO_REMOVE,
    CONF_NEW_HOLIDAY,
    OPTIONS_ACTION,
)
from homeassistant.components.workday.const import (
    CONF_ADD_HOLIDAYS,
    CONF_REMOVE_HOLIDAYS,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry
from tests.components.workday import create_workday_test_data

_LOGGER = logging.getLogger(__name__)


async def test_options(hass: HomeAssistant):
    """Test options flow."""
    mock_data = create_workday_test_data(country="Germany", province="BW")

    config_entry = MockConfigEntry(domain=DOMAIN, data=mock_data)
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.options == {}
    assert hass.states.get("binary_sensor.workday_germany_bw") is not None

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] == "form"
    assert result["step_id"] == "prompt_options"

    # go throw 'add holidays' option
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"], {OPTIONS_ACTION: ACTION_ADD_HOLIDAYS}
    )
    await hass.async_block_till_done()

    _LOGGER.debug("result2: %s", result2)

    assert result2["type"] == "form"
    assert result2["step_id"] == "add_holidays"

    # error validation
    result0 = await hass.config_entries.options.async_configure(
        result2["flow_id"], {CONF_NEW_HOLIDAY: "no_date_value"}
    )

    assert result0["type"] == "form"
    assert result0["step_id"] == "add_holidays"
    assert result0["errors"] == {CONF_NEW_HOLIDAY: "bad_date_format"}

    # add 2020-02-02 holiday
    result3 = await hass.config_entries.options.async_configure(
        result0["flow_id"], {CONF_NEW_HOLIDAY: "2020-02-02"}
    )

    assert result3["type"] == "form"
    assert result3["step_id"] == "add_holidays"
    _LOGGER.debug("data_schema: %s", result3["data_schema"])
    _LOGGER.debug("add_holidays: %s", result3["data_schema"]({})[CONF_ADD_HOLIDAYS])
    temp_list = result3["data_schema"]({})[CONF_ADD_HOLIDAYS]
    assert len(temp_list) == 1

    # add 2020-02-01 holiday
    result4 = await hass.config_entries.options.async_configure(
        result3["flow_id"],
        {
            CONF_NEW_HOLIDAY: "2020-02-01",
            CONF_ADD_HOLIDAYS: temp_list,
        },
    )

    assert result4["type"] == "form"
    assert result4["step_id"] == "add_holidays"
    temp_list = result4["data_schema"]({})[CONF_ADD_HOLIDAYS]
    assert len(temp_list) == 2

    # remove last holiday
    temp_list.pop()
    result5 = await hass.config_entries.options.async_configure(
        result4["flow_id"],
        {
            CONF_ADD_HOLIDAYS: temp_list,
        },
    )

    assert result5["type"] == "create_entry"
    assert result5["data"] == {CONF_ADD_HOLIDAYS: ["2020-02-02"]}
    assert result5["data"].get(CONF_REMOVE_HOLIDAYS) is None

    # another configuration
    result10 = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result10["type"] == "form"
    assert result10["step_id"] == "prompt_options"

    # go throw 'add excludes' option
    result12 = await hass.config_entries.options.async_configure(
        result10["flow_id"], {OPTIONS_ACTION: ACTION_REMOVE_HOLIDAYS}
    )
    await hass.async_block_till_done()

    assert result12["type"] == "form"
    assert result12["step_id"] == "remove_holidays"

    # remove 2020-12-25 holiday
    result13 = await hass.config_entries.options.async_configure(
        result12["flow_id"], {CONF_HOLIDAY_TO_REMOVE: "2020-12-25"}
    )

    assert result13["type"] == "form"
    assert result13["step_id"] == "remove_holidays"
    temp_list = result13["data_schema"]({})[CONF_REMOVE_HOLIDAYS]
    assert len(temp_list) == 1

    # error validation
    result11 = await hass.config_entries.options.async_configure(
        result13["flow_id"], {CONF_HOLIDAY_TO_REMOVE: "no_date_value"}
    )
    await hass.async_block_till_done()

    assert result11["type"] == "form"
    assert result11["step_id"] == "remove_holidays"
    assert result11["errors"] == {CONF_HOLIDAY_TO_REMOVE: "bad_date_format"}

    # save changes
    result14 = await hass.config_entries.options.async_configure(
        result11["flow_id"], {CONF_REMOVE_HOLIDAYS: temp_list}
    )

    assert result14["type"] == "create_entry"
    assert result14["data"].get(CONF_REMOVE_HOLIDAYS) == ["2020-12-25"]
    assert result14["data"].get(CONF_ADD_HOLIDAYS) == ["2020-02-02"]
