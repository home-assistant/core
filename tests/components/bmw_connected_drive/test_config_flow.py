"""Test the for the BMW Connected Drive config flow."""

from copy import deepcopy
from unittest.mock import patch

from bimmer_connected.api.authentication import MyBMWAuthentication
from bimmer_connected.models import MyBMWAPIError, MyBMWAuthError
from httpx import RequestError
import pytest

from homeassistant import config_entries
from homeassistant.components.bmw_connected_drive.config_flow import DOMAIN
from homeassistant.components.bmw_connected_drive.const import (
    CONF_CAPTCHA_TOKEN,
    CONF_READ_ONLY,
    CONF_REFRESH_TOKEN,
)
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    FIXTURE_CAPTCHA_INPUT,
    FIXTURE_CONFIG_ENTRY,
    FIXTURE_GCID,
    FIXTURE_REFRESH_TOKEN,
    FIXTURE_USER_INPUT,
    FIXTURE_USER_INPUT_W_CAPTCHA,
)

from tests.common import MockConfigEntry

FIXTURE_COMPLETE_ENTRY = FIXTURE_CONFIG_ENTRY["data"]
FIXTURE_IMPORT_ENTRY = {**FIXTURE_USER_INPUT, CONF_REFRESH_TOKEN: None}


def login_sideeffect(self: MyBMWAuthentication):
    """Mock logging in and setting a refresh token."""
    self.refresh_token = FIXTURE_REFRESH_TOKEN
    self.gcid = FIXTURE_GCID


async def test_show_form(hass: HomeAssistant) -> None:
    """Test that the form is served with no input."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"


async def test_authentication_error(hass: HomeAssistant) -> None:
    """Test we show user form on MyBMW authentication error."""

    with patch(
        "bimmer_connected.api.authentication.MyBMWAuthentication.login",
        side_effect=MyBMWAuthError("Login failed"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=deepcopy(FIXTURE_USER_INPUT_W_CAPTCHA),
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "invalid_auth"}


async def test_connection_error(hass: HomeAssistant) -> None:
    """Test we show user form on MyBMW API error."""

    with patch(
        "bimmer_connected.api.authentication.MyBMWAuthentication.login",
        side_effect=RequestError("Connection reset"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=deepcopy(FIXTURE_USER_INPUT_W_CAPTCHA),
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


async def test_api_error(hass: HomeAssistant) -> None:
    """Test we show user form on general connection error."""

    with patch(
        "bimmer_connected.api.authentication.MyBMWAuthentication.login",
        side_effect=MyBMWAPIError("400 Bad Request"),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=deepcopy(FIXTURE_USER_INPUT_W_CAPTCHA),
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}


@pytest.mark.usefixtures("bmw_fixture")
async def test_captcha_flow_missing_error(hass: HomeAssistant) -> None:
    """Test the external flow with captcha failing once and succeeding the second time."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data=deepcopy(FIXTURE_USER_INPUT),
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "captcha"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_CAPTCHA_TOKEN: " "}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "missing_captcha"}


async def test_full_user_flow_implementation(hass: HomeAssistant) -> None:
    """Test registering an integration and finishing flow works."""
    with (
        patch(
            "bimmer_connected.api.authentication.MyBMWAuthentication.login",
            side_effect=login_sideeffect,
            autospec=True,
        ),
        patch(
            "homeassistant.components.bmw_connected_drive.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=deepcopy(FIXTURE_USER_INPUT),
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "captcha"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_CAPTCHA_INPUT
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == FIXTURE_COMPLETE_ENTRY[CONF_USERNAME]
        assert result["data"] == FIXTURE_COMPLETE_ENTRY

        assert len(mock_setup_entry.mock_calls) == 1


async def test_options_flow_implementation(hass: HomeAssistant) -> None:
    """Test config flow options."""
    with (
        patch(
            "bimmer_connected.account.MyBMWAccount.get_vehicles",
            return_value=[],
        ),
        patch(
            "homeassistant.components.bmw_connected_drive.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        config_entry_args = deepcopy(FIXTURE_CONFIG_ENTRY)
        config_entry = MockConfigEntry(**config_entry_args)
        config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        result = await hass.config_entries.options.async_init(config_entry.entry_id)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "account_options"

        result = await hass.config_entries.options.async_configure(
            result["flow_id"],
            user_input={CONF_READ_ONLY: True},
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"] == {
            CONF_READ_ONLY: True,
        }

        assert len(mock_setup_entry.mock_calls) == 2


async def test_reauth(hass: HomeAssistant) -> None:
    """Test the reauth form."""
    with (
        patch(
            "bimmer_connected.api.authentication.MyBMWAuthentication.login",
            side_effect=login_sideeffect,
            autospec=True,
        ),
        patch(
            "homeassistant.components.bmw_connected_drive.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        wrong_password = "wrong"

        config_entry_with_wrong_password = deepcopy(FIXTURE_CONFIG_ENTRY)
        config_entry_with_wrong_password["data"][CONF_PASSWORD] = wrong_password

        config_entry = MockConfigEntry(**config_entry_with_wrong_password)
        config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert config_entry.data == config_entry_with_wrong_password["data"]

        result = await config_entry.start_reauth_flow(hass)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "change_password"
        assert set(result["data_schema"].schema) == {CONF_PASSWORD}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: FIXTURE_USER_INPUT[CONF_PASSWORD]}
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "captcha"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_CAPTCHA_INPUT
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reauth_successful"
        assert config_entry.data == FIXTURE_COMPLETE_ENTRY

        assert len(mock_setup_entry.mock_calls) == 2


async def test_reconfigure(hass: HomeAssistant) -> None:
    """Test the reconfiguration form."""
    with patch(
        "bimmer_connected.api.authentication.MyBMWAuthentication.login",
        side_effect=login_sideeffect,
        autospec=True,
    ):
        config_entry = MockConfigEntry(**FIXTURE_CONFIG_ENTRY)
        config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        result = await config_entry.start_reconfigure_flow(hass)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "change_password"
        assert set(result["data_schema"].schema) == {CONF_PASSWORD}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_PASSWORD: FIXTURE_USER_INPUT[CONF_PASSWORD]}
        )
        await hass.async_block_till_done()

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "captcha"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_CAPTCHA_INPUT
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"
        assert config_entry.data == FIXTURE_COMPLETE_ENTRY
