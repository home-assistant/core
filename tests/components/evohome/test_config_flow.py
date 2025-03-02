"""Tests for config flow for the Evohome integration."""

from __future__ import annotations

from http import HTTPStatus
from unittest.mock import patch

import evohomeasync2 as ec2
import pytest

from homeassistant.components.evohome import CONFIG_SCHEMA
from homeassistant.components.evohome.config_flow import (
    DEFAULT_OPTIONS,
    EvoConfigFileDictT,
)
from homeassistant.components.evohome.const import (
    CONF_HIGH_PRECISION,
    CONF_LOCATION_IDX,
    DEFAULT_HIGH_PRECISION,
    DOMAIN,
)
from homeassistant.config_entries import (
    SOURCE_IMPORT,
    SOURCE_USER,
    ConfigEntryState,
    ConfigFlowResult,
)
from homeassistant.const import CONF_PASSWORD, CONF_SCAN_INTERVAL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import mock_make_request, mock_post_request

from tests.common import MockConfigEntry

EXC_LOCN_503 = ec2.ApiRequestFailedError(
    message=HTTPStatus.SERVICE_UNAVAILABLE.phrase,
    status=HTTPStatus.SERVICE_UNAVAILABLE,
)

EXC_USER_401 = ec2.BadUserCredentialsError(
    message=HTTPStatus.UNAUTHORIZED.phrase,
    status=HTTPStatus.UNAUTHORIZED,
)
EXC_USER_429 = ec2.AuthenticationFailedError(
    message=HTTPStatus.TOO_MANY_REQUESTS.phrase,
    status=HTTPStatus.TOO_MANY_REQUESTS,
)
EXC_USER_502 = ec2.AuthenticationFailedError(
    message=HTTPStatus.BAD_GATEWAY.phrase,
    status=HTTPStatus.BAD_GATEWAY,
)

STEP_LOCN_EXCEPTIONS = {
    "cannot_connect": EXC_LOCN_503,
}

STEP_USER_EXCEPTIONS = {
    "cannot_connect": EXC_USER_502,
    "invalid_auth": EXC_USER_401,
    "rate_exceeded": EXC_USER_429,
}


@pytest.mark.parametrize("error_key", STEP_USER_EXCEPTIONS)
async def test_step_reauth_errors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    error_key: str,
) -> None:
    """Test exceptions raised during step_reauth."""

    config_entry.add_to_hass(hass)

    result = await config_entry.start_reauth_flow(hass)

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "reauth_confirm"

    with patch(
        "evohomeasync2.auth.AbstractTokenManager.fetch_access_token",
        side_effect=STEP_USER_EXCEPTIONS[error_key],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_PASSWORD: "new_password",
            },
        )

        await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "reauth_confirm"
    assert result.get("errors") == {"base": error_key}


@pytest.mark.parametrize("error_key", STEP_USER_EXCEPTIONS)
async def test_step_user_errors(
    hass: HomeAssistant,
    config: EvoConfigFileDictT,
    error_key: str,
) -> None:
    """Test exceptions raised during step_user."""

    with patch(
        "evohomeasync2.auth.AbstractTokenManager.fetch_access_token",
        side_effect=STEP_USER_EXCEPTIONS[error_key],
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={
                CONF_USERNAME: config[CONF_USERNAME],
                CONF_PASSWORD: config[CONF_PASSWORD],
            },
        )

        await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"
    assert result.get("errors") == {"base": error_key}


@pytest.mark.parametrize("error_key", STEP_LOCN_EXCEPTIONS)
async def test_step_location_errors(
    hass: HomeAssistant,
    config: EvoConfigFileDictT,
    install: str,
    error_key: str,
) -> None:
    """Test exceptions raised during step_location."""

    with patch(
        "evohomeasync2.auth.CredentialsManagerBase._post_request",
        mock_post_request(install),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={
                CONF_USERNAME: config[CONF_USERNAME],
                CONF_PASSWORD: config[CONF_PASSWORD],
            },
        )

        await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "location"
    assert result.get("errors") == {}

    with patch(
        "evohome.auth.AbstractAuth._make_request",
        side_effect=STEP_LOCN_EXCEPTIONS[error_key],
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_LOCATION_IDX: config[CONF_LOCATION_IDX],
            },
        )

        await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "location"
    assert result.get("errors") == {"base": error_key}


async def test_step_location_bad_index(
    hass: HomeAssistant,
    config: EvoConfigFileDictT,
    install: str,
) -> None:
    """Test invalid location_idx during step_location."""

    with patch(
        "evohomeasync2.auth.CredentialsManagerBase._post_request",
        mock_post_request(install),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={
                CONF_USERNAME: config[CONF_USERNAME],
                CONF_PASSWORD: config[CONF_PASSWORD],
            },
        )

        await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "location"
    assert result.get("errors") == {}

    with patch(
        "evohome.auth.AbstractAuth._make_request",
        mock_make_request(install),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_LOCATION_IDX: 1e9,  # invalid location_idx
            },
        )

        await hass.async_block_till_done()

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "location"
    assert result.get("errors") == {"base": "bad_location"}


async def test_config_flow(
    hass: HomeAssistant,
    config: EvoConfigFileDictT,  # used only as a source of config data
    install: str,
) -> None:
    """Test a successful config flow."""

    result: ConfigFlowResult = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["handler"] == DOMAIN

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "user"
    assert result.get("errors") == {}

    with patch(
        "evohomeasync2.auth.CredentialsManagerBase._post_request",
        mock_post_request(install),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_USERNAME: config[CONF_USERNAME],
                CONF_PASSWORD: config[CONF_PASSWORD],
            },
        )

    assert result.get("type") is FlowResultType.FORM

    with (
        patch(
            "evohome.auth.AbstractAuth._make_request",
            mock_make_request(install),
        ),
        patch(
            "homeassistant.components.evohome.async_setup_entry", return_value=True
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_LOCATION_IDX: config[CONF_LOCATION_IDX],
            },
        )

        await hass.async_block_till_done()

        assert mock_setup_entry.await_count == 1

    assert result.get("type") is FlowResultType.CREATE_ENTRY

    entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert entry.source == SOURCE_USER
    assert entry.state == ConfigEntryState.LOADED

    assert entry.domain == DOMAIN
    assert entry.title == "Evohome"

    assert {k: v for k, v in entry.data.items() if k != "token_data"} == {
        CONF_USERNAME: config[CONF_USERNAME],
        CONF_PASSWORD: config[CONF_PASSWORD],
        CONF_LOCATION_IDX: config[CONF_LOCATION_IDX],
    }

    assert entry.options == DEFAULT_OPTIONS

    # now the options flow....
    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "init"
    assert result.get("errors") == {}

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_HIGH_PRECISION: not DEFAULT_HIGH_PRECISION,
            CONF_SCAN_INTERVAL: config[CONF_SCAN_INTERVAL].seconds,
        },
    )

    assert result.get("type") is FlowResultType.CREATE_ENTRY

    entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert entry.source == SOURCE_USER
    assert entry.state == ConfigEntryState.LOADED

    assert entry.domain == DOMAIN
    assert entry.title == "Evohome"

    assert {k: v for k, v in entry.data.items() if k != "token_data"} == {
        CONF_USERNAME: config[CONF_USERNAME],
        CONF_PASSWORD: config[CONF_PASSWORD],
        CONF_LOCATION_IDX: config[CONF_LOCATION_IDX],
    }
    assert entry.options == {
        CONF_HIGH_PRECISION: not DEFAULT_HIGH_PRECISION,
        CONF_SCAN_INTERVAL: config[CONF_SCAN_INTERVAL].seconds,
    }


async def test_import_flow(
    hass: HomeAssistant,
    config: EvoConfigFileDictT,
    install: str,
) -> None:
    """Test a successful import flow."""

    result: ConfigFlowResult

    with (
        patch(
            "evohomeasync2.auth.CredentialsManagerBase._post_request",
            mock_post_request(install),
        ),
        patch(
            "evohome.auth.AbstractAuth._make_request",
            mock_make_request(install),
        ),
        patch(
            "homeassistant.components.evohome.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=CONFIG_SCHEMA(config),
        )

        await hass.async_block_till_done()

        assert mock_setup_entry.await_count == 1

    assert result["handler"] == DOMAIN

    assert result.get("type") is FlowResultType.CREATE_ENTRY

    entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert entry.source == SOURCE_IMPORT
    assert entry.state == ConfigEntryState.LOADED

    assert entry.domain == DOMAIN
    assert entry.title == "Evohome"

    assert {k: v for k, v in entry.data.items() if k != "token_data"} == {
        CONF_USERNAME: config[CONF_USERNAME],
        CONF_PASSWORD: config[CONF_PASSWORD],
        CONF_LOCATION_IDX: config[CONF_LOCATION_IDX],
    }
    assert entry.options == {
        CONF_HIGH_PRECISION: True,  # True for imports
        CONF_SCAN_INTERVAL: config[CONF_SCAN_INTERVAL].seconds,
    }


async def test_reauth_flow(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    install: str,
) -> None:
    """Test a successful reauth flow."""

    config_entry.add_to_hass(hass)

    result = await config_entry.start_reauth_flow(hass)

    assert result.get("type") is FlowResultType.FORM
    assert result.get("step_id") == "reauth_confirm"

    with patch(
        "evohomeasync2.auth.CredentialsManagerBase._post_request",
        mock_post_request(install),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_PASSWORD: "new_password",
            },
        )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "reauth_successful"

    assert len(hass.config_entries.async_entries()) == 1
    assert config_entry.data[CONF_PASSWORD] == "new_password"


async def test_abort_single_instance_allowed(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
) -> None:
    """Test that only one Evohome config_entry is allowed."""

    # load the first entry
    config_entry.add_to_hass(hass)

    # attempt to create a second entry
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "single_instance_allowed"
