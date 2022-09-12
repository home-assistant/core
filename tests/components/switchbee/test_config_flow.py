"""Test the SwitchBee Smart Home config flow."""
from unittest.mock import patch

from homeassistant import config_entries
from homeassistant.components.switchbee.config_flow import DeviceType, SwitchBeeError
from homeassistant.components.switchbee.const import CONF_SWITCHES_AS_LIGHTS, DOMAIN
from homeassistant.const import CONF_DEVICES, CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import RESULT_TYPE_FORM, FlowResultType

from . import MOCK_FAILED_TO_LOGIN_MSG, MOCK_GET_CONFIGURATION, MOCK_INVALID_TOKEN_MGS

from tests.common import MockConfigEntry


async def test_form(hass):
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] == {}

    with patch(
        "switchbee.api.CentralUnitAPI.get_configuration",
        return_value=MOCK_GET_CONFIGURATION,
    ), patch(
        "homeassistant.components.switchbee.async_setup_entry",
        return_value=True,
    ), patch(
        "switchbee.api.CentralUnitAPI.fetch_states", return_value=None
    ), patch(
        "switchbee.api.CentralUnitAPI._login", return_value=None
    ):

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                CONF_SWITCHES_AS_LIGHTS: False,
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "1.1.1.1"
    assert result2["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
        CONF_SWITCHES_AS_LIGHTS: False,
    }


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "switchbee.api.CentralUnitAPI._login",
        side_effect=SwitchBeeError(MOCK_FAILED_TO_LOGIN_MSG),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                CONF_SWITCHES_AS_LIGHTS: False,
            },
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "switchbee.api.CentralUnitAPI._login",
        side_effect=SwitchBeeError(MOCK_INVALID_TOKEN_MGS),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                CONF_SWITCHES_AS_LIGHTS: False,
            },
        )

    assert result2["type"] == RESULT_TYPE_FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_error(hass):
    """Test we handle an unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "switchbee.api.CentralUnitAPI._login",
        side_effect=Exception,
    ):
        form_result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                CONF_SWITCHES_AS_LIGHTS: False,
            },
        )

    assert form_result["type"] == RESULT_TYPE_FORM
    assert form_result["errors"] == {"base": "unknown"}


async def test_form_entry_exists(hass):
    """Test we handle an already existing entry."""
    MockConfigEntry(
        unique_id="a8:21:08:e7:67:b6",
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
            CONF_SWITCHES_AS_LIGHTS: False,
        },
        title="1.1.1.1",
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch("switchbee.api.CentralUnitAPI._login", return_value=None), patch(
        "homeassistant.components.switchbee.async_setup_entry",
        return_value=True,
    ), patch(
        "switchbee.api.CentralUnitAPI.get_configuration",
        return_value=MOCK_GET_CONFIGURATION,
    ), patch(
        "switchbee.api.CentralUnitAPI.fetch_states", return_value=None
    ):
        form_result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.2.2.2",
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
                CONF_SWITCHES_AS_LIGHTS: False,
            },
        )

    assert form_result["type"] == FlowResultType.ABORT
    assert form_result["reason"] == "already_configured"


async def test_option_flow(hass):
    """Test config flow options."""
    entry = MockConfigEntry(
        unique_id="a8:21:08:e7:67:b6",
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_USERNAME: "test-username",
            CONF_PASSWORD: "test-password",
            CONF_SWITCHES_AS_LIGHTS: False,
        },
        title="1.1.1.1",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    assert result["type"] == "form"
    assert result["step_id"] == "init"
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_DEVICES: [DeviceType.Switch.display, DeviceType.GroupSwitch.display],
        },
    )
    assert result["type"] == "create_entry"
    assert result["data"] == {
        CONF_DEVICES: [DeviceType.Switch.display, DeviceType.GroupSwitch.display],
    }
