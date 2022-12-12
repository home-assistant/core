"""Test the Honeygain config flow."""
from json import JSONDecodeError
from unittest.mock import patch

import pytest

from homeassistant import config_entries
from homeassistant.components.honeygain.config_flow import (
    CannotConnect,
    HoneygainHub,
    InvalidAuth,
    validate_input,
)
from homeassistant.components.honeygain.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType


@pytest.fixture
async def config_flow(hass: HomeAssistant):
    """Fixture represent the Config Flow."""
    return await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )


@pytest.fixture
def test_user() -> dict:
    """Fixture to represent test data."""
    return {"email": "test-email", "password": "test-password"}


async def test_form_is_returned(config_flow) -> None:
    """Test we get the form."""
    assert config_flow["type"] == FlowResultType.FORM
    assert config_flow["errors"] is None


async def test_form_returns_user_input(
    config_flow, test_user, hass: HomeAssistant
) -> None:
    """Test the user's input is stored in the data object."""
    with patch(
        "homeassistant.components.honeygain.config_flow.HoneygainHub.authenticate",
        return_value=True,
    ), patch(
        "homeassistant.components.honeygain.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            config_flow["flow_id"], test_user
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "test-email"
    assert result["data"] == test_user
    assert len(mock_setup_entry.mock_calls) == 1


def test_authenticate_returns_true_on_valid_auth(test_user, hass: HomeAssistant):
    """Test `authenticate` returns True with valid credentials."""
    honeygain_hub = HoneygainHub()
    with patch(
        "pyHoneygain.HoneyGain.login",
        return_value=True,
    ):
        assert honeygain_hub.authenticate(test_user["email"], test_user["password"])


def test_authenticate_raises_invalid_auth_error(test_user, hass: HomeAssistant):
    """Test `authenticate` returns False with invalid credentials."""
    honeygain_hub = HoneygainHub()
    with patch(
        "pyHoneygain.HoneyGain.login",
        side_effect=KeyError,
    ):
        with pytest.raises(InvalidAuth):
            honeygain_hub.authenticate(test_user["email"], test_user["password"])


async def test_form_invalid_auth(config_flow, test_user, hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    with patch(
        "homeassistant.components.honeygain.config_flow.HoneygainHub.authenticate",
        side_effect=InvalidAuth,
    ):
        result = await hass.config_entries.flow.async_configure(
            config_flow["flow_id"], test_user
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_credential_validation_raises_invalid_auth(
    config_flow, test_user, hass: HomeAssistant
) -> None:
    """Test we handle invalid auth."""
    with patch(
        "homeassistant.components.honeygain.config_flow.HoneygainHub.authenticate",
        return_value=False,
    ):
        with pytest.raises(InvalidAuth):
            await validate_input(hass, test_user)


def test_authenticate_raises_cannot_connect_error(test_user, hass: HomeAssistant):
    """Test `authenticate` raises CannotConnect error."""
    honeygain_hub = HoneygainHub()
    with patch(
        "pyHoneygain.HoneyGain.login",
        side_effect=JSONDecodeError(msg="Error", doc="<error>", pos=1),
    ):
        with pytest.raises(CannotConnect):
            honeygain_hub.authenticate(test_user["email"], test_user["password"])


async def test_form_cannot_connect(config_flow, test_user, hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    with patch(
        "homeassistant.components.honeygain.config_flow.HoneygainHub.authenticate",
        side_effect=CannotConnect,
    ):
        result = await hass.config_entries.flow.async_configure(
            config_flow["flow_id"], test_user
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_error(config_flow, test_user, hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    with patch(
        "homeassistant.components.honeygain.config_flow.HoneygainHub.authenticate",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            config_flow["flow_id"], test_user
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}
