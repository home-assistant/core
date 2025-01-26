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
from homeassistant.const import CONF_PASSWORD, CONF_REGION, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import (
    BIMMER_CONNECTED_LOGIN_PATCH,
    BIMMER_CONNECTED_VEHICLE_PATCH,
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


async def test_full_user_flow_implementation(hass: HomeAssistant) -> None:
    """Test registering an integration and finishing flow works."""
    with (
        patch(
            BIMMER_CONNECTED_LOGIN_PATCH,
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
        assert (
            result["result"].unique_id
            == f"{FIXTURE_USER_INPUT[CONF_REGION]}-{FIXTURE_USER_INPUT[CONF_USERNAME]}"
        )

        assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("side_effect", "error"),
    [
        (MyBMWAuthError("Login failed"), "invalid_auth"),
        (RequestError("Connection reset"), "cannot_connect"),
        (MyBMWAPIError("400 Bad Request"), "cannot_connect"),
    ],
)
async def test_error_display_with_successful_login(
    hass: HomeAssistant, side_effect: Exception, error: str
) -> None:
    """Test we show user form on MyBMW authentication error and are still able to succeed."""

    with patch(
        BIMMER_CONNECTED_LOGIN_PATCH,
        side_effect=side_effect,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=deepcopy(FIXTURE_USER_INPUT_W_CAPTCHA),
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": error}

    with (
        patch(
            BIMMER_CONNECTED_LOGIN_PATCH,
            side_effect=login_sideeffect,
            autospec=True,
        ),
        patch(
            "homeassistant.components.bmw_connected_drive.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            deepcopy(FIXTURE_USER_INPUT),
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "captcha"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], FIXTURE_CAPTCHA_INPUT
        )

        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["title"] == FIXTURE_COMPLETE_ENTRY[CONF_USERNAME]
        assert result["data"] == FIXTURE_COMPLETE_ENTRY
        assert (
            result["result"].unique_id
            == f"{FIXTURE_USER_INPUT[CONF_REGION]}-{FIXTURE_USER_INPUT[CONF_USERNAME]}"
        )

        assert len(mock_setup_entry.mock_calls) == 1


async def test_unique_id_existing(hass: HomeAssistant) -> None:
    """Test registering an integration and when the unique id already exists."""

    mock_config_entry = MockConfigEntry(**FIXTURE_CONFIG_ENTRY)
    mock_config_entry.add_to_hass(hass)

    with (
        patch(
            BIMMER_CONNECTED_LOGIN_PATCH,
            side_effect=login_sideeffect,
            autospec=True,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_USER},
            data=deepcopy(FIXTURE_USER_INPUT),
        )

        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "already_configured"


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


async def test_options_flow_implementation(hass: HomeAssistant) -> None:
    """Test config flow options."""
    with (
        patch(
            BIMMER_CONNECTED_VEHICLE_PATCH,
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
            BIMMER_CONNECTED_LOGIN_PATCH,
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
        BIMMER_CONNECTED_LOGIN_PATCH,
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
