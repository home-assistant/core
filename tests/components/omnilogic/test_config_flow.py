"""Test the Omnilogic config flow."""

from collections.abc import Iterator
from contextlib import contextmanager
from unittest.mock import patch

from omnilogic import LoginException, OmniLogicException
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.components.omnilogic.const import DEFAULT_PH_OFFSET, DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

DATA = {"username": "test-username", "password": "test-password"}


@contextmanager
def _patch_success() -> Iterator[None]:
    """Patch a successful connection and setup."""
    with (
        patch(
            "homeassistant.components.omnilogic.config_flow.OmniLogic.connect",
            return_value=True,
        ),
        patch(
            "homeassistant.components.omnilogic.async_setup_entry",
            return_value=None,
        ),
    ):
        yield


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.omnilogic.config_flow.OmniLogic.connect",
            return_value=True,
        ),
        patch(
            "homeassistant.components.omnilogic.async_setup_entry",
            return_value=None,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            DATA,
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Omnilogic"
    assert result2["data"] == DATA
    assert result2["result"].unique_id == "test-username"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_already_configured(hass: HomeAssistant) -> None:
    """Test config flow when Omnilogic component is already setup."""
    MockConfigEntry(domain=DOMAIN, data=DATA).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "single_instance_allowed"


async def test_with_invalid_credentials(hass: HomeAssistant) -> None:
    """Test with invalid credentials."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.omnilogic.OmniLogic.connect",
        side_effect=LoginException,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            DATA,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}

    with _patch_success():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            DATA,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test if invalid response or no connection returned from Hayward."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.omnilogic.OmniLogic.connect",
        side_effect=OmniLogicException,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            DATA,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}

    with _patch_success():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            DATA,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_with_unknown_error(hass: HomeAssistant) -> None:
    """Test with unknown error response from Hayward."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.omnilogic.OmniLogic.connect",
        side_effect=Exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            DATA,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "unknown"}

    with _patch_success():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            DATA,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_option_flow(hass: HomeAssistant) -> None:
    """Test option flow."""
    entry = MockConfigEntry(domain=DOMAIN, data=DATA)
    entry.add_to_hass(hass)

    assert not entry.options

    with patch(
        "homeassistant.components.omnilogic.async_setup_entry", return_value=None
    ):
        result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={"ph_offset": DEFAULT_PH_OFFSET},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == ""
    assert result["data"]["ph_offset"] == DEFAULT_PH_OFFSET


async def test_reauth(hass: HomeAssistant) -> None:
    """Test reauthentication updates the password and reloads the entry."""
    entry = MockConfigEntry(domain=DOMAIN, data=DATA, unique_id="test-username")
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.omnilogic.config_flow.OmniLogic.connect",
            return_value=True,
        ),
        patch(
            "homeassistant.components.omnilogic.async_setup_entry",
            return_value=None,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"password": "new-password"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data == {"username": "test-username", "password": "new-password"}
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        pytest.param(LoginException, "invalid_auth", id="invalid_auth"),
        pytest.param(OmniLogicException, "cannot_connect", id="cannot_connect"),
        pytest.param(Exception, "unknown", id="unknown"),
    ],
)
async def test_reauth_errors(
    hass: HomeAssistant, side_effect: type[Exception], error: str
) -> None:
    """Test reauthentication errors and a successful retry."""
    entry = MockConfigEntry(domain=DOMAIN, data=DATA, unique_id="test-username")
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)

    with patch(
        "homeassistant.components.omnilogic.config_flow.OmniLogic.connect",
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"password": "new-password"}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"
    assert result["errors"] == {"base": error}

    with _patch_success():
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {"password": "new-password"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data == {"username": "test-username", "password": "new-password"}
