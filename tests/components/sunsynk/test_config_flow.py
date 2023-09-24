"""Test the Sunsynk config flow."""
from unittest.mock import patch

import pytest
from sunsynk.client import InvalidCredentialsException
from sunsynk.inverter import Inverter

from homeassistant import config_entries
from homeassistant.components.sunsynk.config_flow import (
    CannotConnect,
    InvalidAuth,
    SunsynkHub,
    validate_input,
)
from homeassistant.components.sunsynk.const import DATA_INVERTER_SN, DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

SUNSYNK_CLIENT_CREATE = "sunsynk.client.SunsynkClient.create"
SUNSYNK_GET_INVERTERS = "sunsynk.client.SunsynkClient.get_inverters"

SUNSYNK_HUB_AUTHENTICATE = (
    "homeassistant.components.sunsynk.config_flow.SunsynkHub.authenticate"
)
SUNSYNK_HUB_GET_INVERTERS = (
    "homeassistant.components.sunsynk.config_flow.SunsynkHub.get_inverters"
)


async def test_sunsunk_hub_authenticate_success(hass: HomeAssistant) -> None:
    """Test SunsynkHub can authenticate successfully."""
    with patch(SUNSYNK_CLIENT_CREATE, return_value=True):
        hub = SunsynkHub()
        assert (await hub.authenticate("myuser", "letmein")) is True


async def test_sunsunk_hub_authenticate_failure(hass: HomeAssistant) -> None:
    """Test SunsynkHub can handle authentication failure."""
    with patch(SUNSYNK_CLIENT_CREATE) as client_create:
        client_create.side_effect = InvalidCredentialsException()
        hub = SunsynkHub()
        assert (await hub.authenticate("myuser", "invalidpassword")) is False


async def test_sunsunk_hub_get_inverters(hass: HomeAssistant) -> None:
    """Test SunsynkHub can retrieve inverters when logged in."""
    with patch(SUNSYNK_CLIENT_CREATE, return_value=True), patch(
        SUNSYNK_HUB_GET_INVERTERS, return_value=[Inverter({"sn": "INV123"})]
    ):
        hub = SunsynkHub()
        assert len(await hub.get_inverters()) == 1


async def test_sunsunk_hub_get_inverters_unauthenticated(hass: HomeAssistant) -> None:
    """Test SunsynkHub returns an empty list if not logged in."""
    hub = SunsynkHub()
    assert (await hub.get_inverters()) == []


async def test_validate_input_handles_bad_data(hass: HomeAssistant) -> None:
    """Test validate_input handles bad data argument."""
    with pytest.raises(InvalidAuth):
        await validate_input(hass, {})


async def test_validate_input_authenticates(hass: HomeAssistant) -> None:
    """Test validate_input authenticates successfully."""
    with patch(SUNSYNK_HUB_AUTHENTICATE, return_value=True):
        data = {CONF_USERNAME: "myuser", CONF_PASSWORD: "letmein"}
        assert isinstance(await validate_input(hass, data), SunsynkHub)


async def test_validate_input_handles_auth_failure(hass: HomeAssistant) -> None:
    """Test validate_input authenticates handles auth failure."""
    with patch(SUNSYNK_HUB_AUTHENTICATE, return_value=False):
        data = {CONF_USERNAME: "myuser", CONF_PASSWORD: "invalidpwd"}
        with pytest.raises(InvalidAuth):
            await validate_input(hass, data)


async def test_form_configures_inverter_integration(hass: HomeAssistant) -> None:
    """Test that the user step form is displayed."""
    initial_form_result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert initial_form_result["type"] == FlowResultType.FORM
    assert initial_form_result["step_id"] == "user"
    assert initial_form_result["errors"] is None

    with patch(SUNSYNK_HUB_AUTHENTICATE, return_value=True) as mock_authenticate, patch(
        SUNSYNK_HUB_GET_INVERTERS, return_value=[Inverter({"sn": "INV123"})]
    ) as mock_get_inverters, patch(
        "homeassistant.components.sunsynk.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        user_form_result = await hass.config_entries.flow.async_configure(
            initial_form_result["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert user_form_result["type"] == FlowResultType.FORM
    assert user_form_result["step_id"] == "inverter"
    assert len(mock_authenticate.mock_calls) == 1
    assert len(mock_get_inverters.mock_calls) == 1

    with patch(
        "homeassistant.components.sunsynk.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        inverter_form_result = await hass.config_entries.flow.async_configure(
            initial_form_result["flow_id"],
            {
                DATA_INVERTER_SN: "INV123",
            },
        )
        await hass.async_block_till_done()

    assert inverter_form_result["type"] == FlowResultType.CREATE_ENTRY
    assert inverter_form_result["title"] == "Inverter INV123"
    assert inverter_form_result["data"] == {
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
        DATA_INVERTER_SN: "INV123",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(SUNSYNK_HUB_AUTHENTICATE, side_effect=InvalidAuth):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(SUNSYNK_HUB_AUTHENTICATE, side_effect=CannotConnect):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
