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


async def test_form(hass):
    """Test we get the form."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.enasolar.async_setup_entry", return_value=True
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._try_connect",
        return_value=True,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._get_serial_no",
        return_value=1234567890,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._get_max_output",
        return_value=3.8,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._get_dc_strings",
        return_value=1,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._get_capability",
        return_value=256,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": DEFAULT_HOST,
                "name": NAME,
                "sun_up": "06:00",
                "sun_down": "22:00",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == "form"
    assert result2["step_id"] == "inverter"
    assert len(mock_setup_entry.mock_calls) == 1


def init_config_flow(hass):
    """Init a configuration flow."""
    flow = config_flow.EnaSolarConfigFlow()
    flow.hass = hass
    return flow


async def test_user(hass):
    """Test user config."""
    flow = init_config_flow(hass)

    with patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow.async_set_unique_id",
        return_value=True,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._try_connect",
        return_value=True,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._get_serial_no",
        return_value=1234567890,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._get_max_output",
        return_value=3.8,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._get_dc_strings",
        return_value=1,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._get_capability",
        return_value=256,
    ):
        result = await flow.async_step_user()

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow.async_set_unique_id",
        return_value=True,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._try_connect",
        return_value=True,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._get_serial_no",
        return_value=1234567890,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._get_max_output",
        return_value=3.8,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._get_dc_strings",
        return_value=1,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._get_capability",
        return_value=256,
    ):
        result = await flow.async_step_user(
            {
                CONF_HOST: DEFAULT_HOST,
                CONF_NAME: NAME,
                CONF_SUN_UP: DEFAULT_SUN_UP,
                CONF_SUN_DOWN: DEFAULT_SUN_DOWN,
            }
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "inverter"


async def test_inverter(hass):
    """Test user config."""
    flow = init_config_flow(hass)

    with patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow.async_set_unique_id",
        return_value=True,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._try_connect",
        return_value=True,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._get_serial_no",
        return_value=1234567890,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._get_max_output",
        return_value=3.8,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._get_dc_strings",
        return_value=1,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._get_capability",
        return_value=256,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._get_name",
        return_value="My Inverter",
    ):
        result = await flow.async_step_inverter()

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "inverter"

    # test with all provided
    with patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow.async_set_unique_id",
        return_value=True,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._try_connect",
        return_value=True,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._get_serial_no",
        return_value=1234567890,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._get_max_output",
        return_value=3.8,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._get_dc_strings",
        return_value=1,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._get_capability",
        return_value=256,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._get_name",
        return_value="My Inverter",
    ):
        result = await flow.async_step_inverter(
            {
                CONF_MAX_OUTPUT: 3.8,
                CONF_DC_STRINGS: 1,
                CONF_CAPABILITY: 256,
            }
        )
    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["title"] == "My Inverter"
    assert result["data"] == {
        CONF_MAX_OUTPUT: 3.8,
        CONF_DC_STRINGS: 1,
        CONF_CAPABILITY: 256,
    }


async def test_import(hass):
    """Test import step."""
    flow = init_config_flow(hass)

    test_data = {
        CONF_NAME: "My Inverter",
        CONF_HOST: DEFAULT_HOST,
        CONF_SUN_UP: "06:00",
        CONF_SUN_DOWN: "22:00",
    }

    # import with all required fields
    with patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow.async_set_unique_id",
        return_value=True,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._try_connect",
        return_value=True,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._get_serial_no",
        return_value=1234567890,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._get_max_output",
        return_value=3.8,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._get_dc_strings",
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._get_capability",
        return_value=256,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._get_name",
        return_value="My Inverter",
    ):
        result = await flow.async_step_import(test_data)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "inverter"


async def test_abort_if_already_setup(hass):
    """Test we abort if the device is already setup."""
    flow = init_config_flow(hass)
    MockConfigEntry(
        domain="enasolar",
        data={
            CONF_NAME: NAME,
            CONF_HOST: DEFAULT_HOST,
            CONF_SUN_UP: "06:00",
            CONF_SUN_DOWN: "22:00",
        },
    ).add_to_hass(hass)

    test_data = {
        CONF_NAME: "My Other Inverter",
        CONF_HOST: DEFAULT_HOST,
        CONF_SUN_UP: "06:00",
        CONF_SUN_DOWN: "22:00",
    }

    # Should fail, same HOST different NAME (default)
    result = await flow.async_step_import(test_data)
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"

    # Should fail, same HOST and NAME
    result = await flow.async_step_user(test_data)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["errors"] == {CONF_HOST: "already_configured"}

    # SHOULD pass, diff HOST, different NAME
    test_data[CONF_HOST] = "192.168.1.100"
    test_data[CONF_NAME] = "My Other Inverter"
    with patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow.async_set_unique_id",
        return_value=True,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._try_connect",
        return_value=True,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._get_serial_no",
        return_value=1234567890,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._get_max_output",
        return_value=3.8,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._get_dc_strings",
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._get_capability",
        return_value=256,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._get_name",
        return_value="My Inverter",
    ):
        result = await flow.async_step_import(test_data)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "inverter"

    # SHOULD pass, diff HOST, same NAME
    test_data[CONF_HOST] = "my.inverter.otherfqdn"
    test_data[CONF_NAME] = NAME
    with patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow.async_set_unique_id",
        return_value=True,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._try_connect",
        return_value=True,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._get_serial_no",
        return_value=1234567890,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._get_max_output",
        return_value=3.8,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._get_dc_strings",
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._get_capability",
        return_value=256,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._get_name",
        return_value="My Inverter",
    ):
        result = await flow.async_step_import(test_data)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "inverter"
