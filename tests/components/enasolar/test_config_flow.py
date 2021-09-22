"""Test the enasolar config flow."""
from unittest.mock import MagicMock, patch

from aiohttp.client_exceptions import ClientConnectorError, ClientResponseError

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.enasolar import config_flow
from homeassistant.components.enasolar.const import (
    CONF_CAPABILITY,
    CONF_DC_STRINGS,
    CONF_HOST,
    CONF_MAX_OUTPUT,
    CONF_NAME,
    CONF_SUN_DOWN,
    CONF_SUN_UP,
    DOMAIN,
)
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

TEST_NAME = "My Inverter"
GOOD_TEST_HOST = "123.123.123.123"
TEST_DATA = {CONF_HOST: GOOD_TEST_HOST, CONF_NAME: TEST_NAME}
INVERTER_DATA = {CONF_MAX_OUTPUT: 3.8, CONF_DC_STRINGS: 1, CONF_CAPABILITY: 0x107}


async def test_form(hass: HomeAssistant):
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.enasolar.config_flow.pyenasolar.EnaSolar.interogate_inverter",
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=TEST_DATA
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "inverter"


async def test_user(hass: HomeAssistant):
    """Test user config."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.enasolar.config_flow.pyenasolar.EnaSolar.interogate_inverter",
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=TEST_DATA,
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "inverter"

    with patch("homeassistant.components.enasolar.config_flow.pyenasolar.EnaSolar"):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input=INVERTER_DATA,
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
        assert result["data"] == {
            CONF_MAX_OUTPUT: 3.8,
            CONF_DC_STRINGS: 1,
            CONF_CAPABILITY: 263,
            CONF_HOST: GOOD_TEST_HOST,
            CONF_NAME: TEST_NAME,
        }


async def test_user_invalid_host(hass: HomeAssistant):
    """Test use config with an invalid host."""

    with patch(
        "homeassistant.components.enasolar.config_flow.pyenasolar.EnaSolar.interogate_inverter"
    ), patch(
        "homeassistant.components.enasolar.config_flow._get_ip", return_value=None
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=TEST_DATA
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"host": "invalid_host"}


async def test_user_cannot_connect(hass: HomeAssistant):
    """Test user config where cannot connect to inverter."""

    os_error = MagicMock()
    os_error.error = True
    os_error.strerror = True

    with patch(
        "homeassistant.components.enasolar.config_flow.pyenasolar.EnaSolar.interogate_inverter"
    ) as mock:
        mock.side_effect = ClientConnectorError(connection_key=None, os_error=os_error)  # type: ignore
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=TEST_DATA
        )

        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"host": "cannot_connect"}


async def test_user_unexpected_response(hass: HomeAssistant):
    """Test user config where unexpected response."""

    with patch(
        "homeassistant.components.enasolar.config_flow.pyenasolar.EnaSolar.interogate_inverter",
    ) as mock:
        mock.side_effect = ClientResponseError(request_info=None, history=None)  # type: ignore
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=TEST_DATA
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"host": "unexpected_response"}


async def test_user_unknown(hass: HomeAssistant):
    """Test user config unknown response."""
    with patch(
        "homeassistant.components.enasolar.config_flow.pyenasolar.EnaSolar.interogate_inverter",
    ) as mock:
        mock.side_effect = Exception
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}, data=TEST_DATA
        )
        assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
        assert result["step_id"] == "user"
        assert result["errors"] == {"host": "unknown"}


def init_config_flow(hass: HomeAssistant):
    """Init a configuration flow."""
    flow = config_flow.EnaSolarConfigFlow()
    flow.hass = hass
    return flow


async def test_abort_if_already_setup(hass: HomeAssistant):
    """Test we abort if the device is already setup."""
    flow = init_config_flow(hass)
    MockConfigEntry(
        domain="enasolar",
        data={
            CONF_NAME: TEST_NAME,
            CONF_HOST: GOOD_TEST_HOST,
        },
        unique_id=1234567890,
    ).add_to_hass(hass)

    test_data = {CONF_HOST: GOOD_TEST_HOST, CONF_NAME: TEST_NAME}
    # Should fail, same HOST and NAME and S/No

    with patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow.async_set_unique_id",
        return_value=True,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._try_connect",
        return_value=None,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow.get_serial_no",
        return_value=1234567890,
    ):
        result = await flow.async_step_user(test_data)
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"

    # SHOULD pass, same HOST, same NAME, different S/No
    with patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow.async_set_unique_id",
        return_value=True,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._try_connect",
        return_value=None,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow.get_serial_no",
        return_value=987654321,
    ):
        result = await flow.async_step_user(test_data)
    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "inverter"

    test_data[CONF_NAME] = "My Inverter"

    # Should fail, same HOST different NAME (default), same S/No
    with patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow.async_set_unique_id",
        return_value=True,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._try_connect",
        return_value=None,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow.get_serial_no",
        return_value=1234567890,
    ):
        result = await flow.async_step_user(test_data)
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"

    # SHOULD fail, diff HOST, different NAME, same S/No
    test_data[CONF_HOST] = "192.168.1.100"
    test_data[CONF_NAME] = "My Other Inverter"
    with patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow.async_set_unique_id",
        return_value=True,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow._try_connect",
        return_value=None,
    ), patch(
        "homeassistant.components.enasolar.config_flow.EnaSolarConfigFlow.get_serial_no",
        return_value=1234567890,
    ):
        result = await flow.async_step_user(test_data)
    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow(hass):
    """Test config flow options."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "my.inverter.fqdn", CONF_NAME: "My Inverter"},
        options={},
        entry_id=1,
        version=1,
    )
    config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(
        config_entry.entry_id, context={"show_advanced_options": False}
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={CONF_SUN_UP: "06:00", CONF_SUN_DOWN: "22:00"},
    )

    assert result["type"] == data_entry_flow.RESULT_TYPE_CREATE_ENTRY
    assert result["data"] == {CONF_SUN_UP: "06:00", CONF_SUN_DOWN: "22:00"}
