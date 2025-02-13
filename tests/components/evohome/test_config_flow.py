"""Tests for config flow for the Evohome integration."""

from __future__ import annotations

from unittest.mock import patch

import evohomeasync2 as ec2
import pytest

from homeassistant.components.evohome import CONFIG_SCHEMA
from homeassistant.components.evohome.const import (
    CONF_HIGH_PRECISION,
    CONF_LOCATION_IDX,
    DEFAULT_HIGH_PRECISION,
    DEFAULT_LOCATION_IDX,
    DOMAIN,
    SCAN_INTERVAL_DEFAULT,
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
from homeassistant.exceptions import ConfigEntryAuthFailed  # , ConfigEntryNotReady

from .conftest import mock_make_request, mock_post_request


@pytest.mark.parametrize("install", ["minimal"])
async def test_import_flow(
    hass: HomeAssistant,
    config: dict[str, str],
    install: str,
) -> None:
    """Test an import flow."""

    result: ConfigFlowResult

    with (
        patch(
            "evohomeasync2.auth.CredentialsManagerBase._post_request",
            mock_post_request(install),
        ),
        patch("evohome.auth.AbstractAuth._make_request", mock_make_request(install)),
        patch(
            "homeassistant.components.evohome.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=CONFIG_SCHEMA(config.copy()),
        )

        await hass.async_block_till_done()

        assert mock_setup_entry.await_count == 1

    assert result["handler"] == DOMAIN

    assert result.get("type") == FlowResultType.CREATE_ENTRY

    entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert entry.source == SOURCE_IMPORT
    assert entry.state == ConfigEntryState.LOADED

    assert entry.domain == DOMAIN
    assert entry.title == "Evohome"

    assert entry.data == {
        CONF_USERNAME: config[CONF_USERNAME],
        CONF_PASSWORD: config[CONF_PASSWORD],
        CONF_LOCATION_IDX: DEFAULT_LOCATION_IDX,
    }
    assert entry.options == {
        CONF_HIGH_PRECISION: DEFAULT_HIGH_PRECISION,
        CONF_SCAN_INTERVAL: SCAN_INTERVAL_DEFAULT,
    }


@pytest.mark.parametrize("install", ["minimal"])
async def test_config_flow(
    hass: HomeAssistant,
    config: dict[str, str],
    install: str,
) -> None:
    """Test a config flow."""

    result: ConfigFlowResult = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["handler"] == DOMAIN

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "user"
    assert result.get("errors") == {}

    with patch(
        "evohomeasync2.auth.CredentialsManagerBase._post_request",
        mock_post_request(install),
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: config[CONF_USERNAME],
                CONF_PASSWORD: config[CONF_PASSWORD],
            },
        )

        # [
        #     "type",
        #     "flow_id",
        #     "handler",
        #     "data_schema",
        #     "errors",
        #     "description_placeholders",
        #     "last_step",
        #     "preview",
        #     "step_id",
        # ]

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "location"
    assert result.get("errors") == {}

    with (
        patch("evohome.auth.AbstractAuth._make_request", mock_make_request(install)),
        patch(
            "homeassistant.components.evohome.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_LOCATION_IDX: DEFAULT_LOCATION_IDX,
            },
        )

        # [
        #     "type",
        #     "flow_id",
        #     "handler",
        #     "data",
        #     "description",
        #     "description_placeholders",
        #     "context",
        #     "title",
        #     "minor_version",
        #     "options",
        #     "version",
        #     "result",
        # ]

        await hass.async_block_till_done()

        assert mock_setup_entry.await_count == 1

        assert result.get("type") == FlowResultType.CREATE_ENTRY

    entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert entry.source == SOURCE_USER
    assert entry.state == ConfigEntryState.LOADED

    assert entry.domain == DOMAIN
    assert entry.title == "Evohome"

    assert entry.data == {
        CONF_USERNAME: config[CONF_USERNAME],
        CONF_PASSWORD: config[CONF_PASSWORD],
        CONF_LOCATION_IDX: DEFAULT_LOCATION_IDX,
    }
    # assert entry.options == {
    #     CONF_HIGH_PRECISION: DEFAULT_HIGH_PRECISION,
    #     CONF_SCAN_INTERVAL: SCAN_INTERVAL_DEFAULT,
    # }


async def test_login_error(
    hass: HomeAssistant,
    config: dict[str, str],
) -> None:
    """Test login error."""

    with (
        patch(
            "evohomeasync2.auth.CredentialsManagerBase._post_request",
            side_effect=ec2.BadUserCredentialsError("Bad user credentials"),
        ),
        pytest.raises(ConfigEntryAuthFailed),
    ):
        await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={
                CONF_USERNAME: config[CONF_USERNAME],
                CONF_PASSWORD: config[CONF_PASSWORD],
            },
        )
