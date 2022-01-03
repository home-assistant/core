"""Test the enasolar config flow."""
from unittest.mock import patch

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.enasolar import config_flow
from homeassistant.components.enasolar.const import (
    CONF_CAPABILITY,
    CONF_DC_STRINGS,
    CONF_HOST,
    CONF_MAX_OUTPUT,
    CONF_NAME,
    CONF_SUN_DOWN,
    CONF_SUN_UP,
    DEFAULT_HOST,
    DEFAULT_SUN_DOWN,
    DEFAULT_SUN_UP,
    DOMAIN,
)

from tests.common import MockConfigEntry

NAME = "My Inverter"
IP_ADDRESS = "1.2.3.4"
SERIAL_NO = 1234567890


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.enasolar.async_setup_entry", return_value=True
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._try_connect",
        return_value=None,
    ), patch(
        "homeassistant.components.enasolar.config_flow._get_ip", return_value=IP_ADDRESS
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: DEFAULT_HOST,
                CONF_NAME: NAME,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["step_id"] == "inverter"
    assert result2["errors"] == {}
    assert len(mock_setup_entry.mock_calls) == 1


def init_config_flow(hass):
    """Init a configuration flow."""
    flow = config_flow.EnaSolarConfigFlow()
    flow.hass = hass
    return flow


async def test_user(hass):
    """Test user config."""
    flow = init_config_flow(hass)

    #   Firstly, No input should just return the form
    result = await flow.async_step_user()

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    #   With supposedly valid host and Name
    with patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow.async_set_unique_id",
        return_value=True,
    ), patch(
        "homeassistant.components.enasolar.config_flow._get_ip", return_value=IP_ADDRESS
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._try_connect",
        return_value=None,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow.get_serial_no",
        return_value=SERIAL_NO,
    ):
        result = await flow.async_step_user({CONF_HOST: DEFAULT_HOST, CONF_NAME: NAME})

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "inverter"


async def test_inverter(hass):
    """Test user config."""
    flow = init_config_flow(hass)

    #   Firstly with no data should return the form
    result = await flow.async_step_inverter()

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "inverter"

    #   With all valid data provided
    with patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow.async_set_unique_id",
        return_value=True,
    ), patch(
        "homeassistant.components.enasolar.config_flow._get_ip",
        return_value=IP_ADDRESS,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._try_connect",
        return_value=None,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow.get_serial_no",
        return_value=SERIAL_NO,
    ):
        result = await flow.async_step_user({CONF_HOST: DEFAULT_HOST, CONF_NAME: NAME})
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "inverter"

    with patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow.async_set_unique_id",
        return_value=True,
    ), patch(
        "homeassistant.components.enasolar.config_flow._get_ip",
        return_value=IP_ADDRESS,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._try_connect",
        return_value=None,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow.get_serial_no",
        return_value=SERIAL_NO,
    ):
        result = await flow.async_step_inverter(
            {CONF_MAX_OUTPUT: 3.8, CONF_DC_STRINGS: 1, CONF_CAPABILITY: 256}
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "My Inverter"
    assert result["data"] == {
        CONF_MAX_OUTPUT: 3.8,
        CONF_DC_STRINGS: 1,
        CONF_CAPABILITY: 256,
        CONF_HOST: DEFAULT_HOST,
        CONF_NAME: NAME,
    }

    #   With all invalid data provided
    with patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow.async_set_unique_id",
        return_value=True,
    ), patch(
        "homeassistant.components.enasolar.config_flow._get_ip",
        return_value=IP_ADDRESS,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._try_connect",
        return_value=None,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow.get_serial_no",
        return_value=SERIAL_NO,
    ):
        result = await flow.async_step_inverter(
            {CONF_MAX_OUTPUT: 8, CONF_DC_STRINGS: 3, CONF_CAPABILITY: 512}
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {"capability": "capability_invalid"}


async def test_abort_if_already_setup(hass):
    """Test we abort if the device is already setup."""
    flow = init_config_flow(hass)
    MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_NAME: NAME,
            CONF_HOST: DEFAULT_HOST,
            CONF_CAPABILITY: 0,
            CONF_MAX_OUTPUT: 4,
            CONF_DC_STRINGS: 2,
        },
        options={CONF_SUN_UP: DEFAULT_SUN_UP, CONF_SUN_DOWN: DEFAULT_SUN_DOWN},
        unique_id=SERIAL_NO,
    ).add_to_hass(hass)

    with patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow.async_set_unique_id",
        return_value=True,
    ), patch(
        "homeassistant.components.enasolar.config_flow._get_ip",
        return_value=IP_ADDRESS,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._try_connect",
        return_value=None,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow.get_serial_no",
        return_value=SERIAL_NO,
    ):
        result = await flow.async_step_user({CONF_HOST: DEFAULT_HOST, CONF_NAME: NAME})
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_options(hass):
    """Test updating options."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_NAME: NAME,
            CONF_HOST: DEFAULT_HOST,
            CONF_CAPABILITY: 0,
            CONF_MAX_OUTPUT: 4,
            CONF_DC_STRINGS: 2,
        },
        options={CONF_SUN_UP: DEFAULT_SUN_UP, CONF_SUN_DOWN: DEFAULT_SUN_DOWN},
        unique_id=SERIAL_NO,
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(config_entry.entry_id)

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_SUN_UP: "7:00", CONF_SUN_DOWN: "19:00"}
    )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result2["data"] == {CONF_SUN_UP: "7:00", CONF_SUN_DOWN: "19:00"}

    #   Invalid times
    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result2 = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input={CONF_SUN_UP: "27:00", CONF_SUN_DOWN: "26:00"}
    )

    assert result2["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result2["errors"] == {
        CONF_SUN_UP: "time_invalid",
        CONF_SUN_DOWN: "time_invalid",
    }
