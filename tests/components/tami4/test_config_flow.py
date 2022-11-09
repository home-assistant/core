"""Tests for the Tami4 config flow."""
from unittest.mock import patch

from Tami4EdgeAPI.device import Device

from homeassistant import config_entries, data_entry_flow
from homeassistant.components.tami4.const import CONF_PHONE, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    user_form = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert user_form["type"] == FlowResultType.FORM
    assert user_form["step_id"] == "user"
    assert user_form["handler"] == DOMAIN
    assert user_form["errors"] == {}

    with patch(
        "homeassistant.components.tami4.config_flow.Tami4EdgeAPI.request_otp",
        return_value=None,
    ), patch(
        "homeassistant.components.tami4.async_setup_entry",
        return_value=True,
    ):
        otp_form = await hass.config_entries.flow.async_configure(
            user_form["flow_id"],
            {CONF_PHONE: "+972511111111"},
        )
        await hass.async_block_till_done()

    assert otp_form["type"] == FlowResultType.FORM
    assert otp_form["step_id"] == "otp"
    assert otp_form["handler"] == DOMAIN
    assert otp_form["errors"] == {}

    with patch(
        "homeassistant.components.tami4.config_flow.Tami4EdgeAPI.submit_otp",
        return_value="",
    ), patch(
        "homeassistant.components.tami4.config_flow.Tami4EdgeAPI._get_devices",
        return_value=[
            Device(
                id=1,
                name="device name",
                connected=True,
                last_heart_beat=1,
                psn="psn",
                type="type",
                device_firmware="firmware",
            )
        ],
    ), patch(
        "homeassistant.components.tami4.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            otp_form["flow_id"],
            {"otp": "1111"},
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["handler"] == DOMAIN
    # assert result["data"] == {CONF_REFRESH_TOKEN: ""}
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_phone(hass: HomeAssistant) -> None:
    """Test we handle invalid phone number."""

    user_form = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.tami4.config_flow.Tami4EdgeAPI.request_otp",
        return_value=None,
    ), patch(
        "homeassistant.components.tami4.async_setup_entry",
        return_value=True,
    ):
        otp_form = await hass.config_entries.flow.async_configure(
            user_form["flow_id"],
            {CONF_PHONE: "9999"},
        )
        await hass.async_block_till_done()

    assert otp_form["type"] == data_entry_flow.FlowResultType.FORM
    assert otp_form["errors"] == {"base": "invalid_phone"}
