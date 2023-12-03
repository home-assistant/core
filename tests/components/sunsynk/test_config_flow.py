"""Test the Sunsynk config flow."""
from unittest.mock import patch

import pytest
from sunsynk.client import InvalidCredentialsException, SunsynkClient
from sunsynk.inverter import Inverter

from homeassistant import config_entries
from homeassistant.components.sunsynk.config_flow import (
    CannotConnect,
    InvalidAuth,
    SunsynkHub,
    validate_input,
)
from homeassistant.components.sunsynk.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

SUNSYNK_HUB_AUTHENTICATE = (
    "homeassistant.components.sunsynk.config_flow.SunsynkHub.authenticate"
)
SUNSYNK_HUB_GET_INVERTERS = (
    "homeassistant.components.sunsynk.config_flow.SunsynkHub.get_inverters"
)


class MockSunsynkClient(SunsynkClient):
    """Mock of the SunsynkClient."""

    @classmethod
    async def create(cls, username: str, password: str) -> SunsynkClient:
        """Create an instance of MockSunsynkClient."""
        return MockSunsynkClient(username=username, password=password)

    def __init__(self):
        """Provide blank, stubbed constructor for mock."""
        pass

    async def login(self) -> SunsynkClient:
        """Mock the login process."""
        if self.username == "myuser" and self.password == "letmein":
            return self
        raise InvalidCredentialsException()

    async def get_inverters(self) -> list[Inverter]:
        """Return a mock inverter if mock credentials are valid."""
        if self.username == "myuser" and self.password == "letmein":
            return [Inverter({"sn": "INV123"})]
        return []


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
    assert initial_form_result["errors"] == {}

    with patch(SUNSYNK_HUB_AUTHENTICATE, return_value=True) as mock_authenticate, patch(
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

    assert user_form_result["type"] == FlowResultType.CREATE_ENTRY
    assert user_form_result["title"] == "test-username"
    assert user_form_result["data"] == {
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }
    assert len(mock_authenticate.mock_calls) == 1
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
