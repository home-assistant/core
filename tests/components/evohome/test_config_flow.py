"""Tests for config flow for the Evohome integration."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from homeassistant.components.evohome.const import (
    CONF_LOCATION_IDX,
    DEFAULT_LOCATION_IDX,
    DOMAIN,
    SCAN_INTERVAL_MINIMUM,
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


@pytest.mark.parametrize("install", ["minimal"])
async def test_import_flow(
    hass: HomeAssistant,
    config: dict[str, str],
    install: str,
) -> None:
    """Test an import flow."""

    # Mock the config data that would normally come from a YAML file or similar
    import_config = config.copy()

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
        result: ConfigFlowResult = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=import_config,
        )

        await hass.async_block_till_done()

        assert mock_setup_entry.await_count == 1

    assert result["handler"] == DOMAIN

    assert result["type"] == FlowResultType.CREATE_ENTRY

    entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert entry.source == SOURCE_IMPORT
    assert entry.state is ConfigEntryState.LOADED

    assert entry.domain == DOMAIN
    assert entry.title == "Evohome"

    assert entry.data == {
        CONF_USERNAME: config[CONF_USERNAME],
        CONF_PASSWORD: config[CONF_PASSWORD],
        CONF_LOCATION_IDX: DEFAULT_LOCATION_IDX,
        CONF_SCAN_INTERVAL: SCAN_INTERVAL_MINIMUM,
    }


@pytest.mark.parametrize("install", ["minimal"])
async def test_form(
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

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] is None  # == {}

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

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "location"
    assert result["errors"] is None  # == {}

    with patch("evohome.auth.AbstractAuth._make_request", mock_make_request(install)):
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
        #     "data_schema",
        #     "errors",
        #     "description_placeholders",
        #     "last_step",
        #     "preview",
        #     "step_id",
        # ]

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "scan_interval"
    assert result["errors"] is None  # == {}

    with patch(
        "homeassistant.components.evohome.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_SCAN_INTERVAL: SCAN_INTERVAL_MINIMUM,
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

    assert result["type"] == FlowResultType.CREATE_ENTRY

    entry = hass.config_entries.async_entries(DOMAIN)[0]

    assert entry.source == SOURCE_USER
    assert entry.state is ConfigEntryState.LOADED

    assert entry.domain == DOMAIN
    assert entry.title == "Evohome"

    assert entry.data == {
        CONF_USERNAME: config[CONF_USERNAME],
        CONF_PASSWORD: config[CONF_PASSWORD],
        CONF_LOCATION_IDX: DEFAULT_LOCATION_IDX,
        CONF_SCAN_INTERVAL: SCAN_INTERVAL_MINIMUM,
    }


# async def test_login_error(hass: HomeAssistant) -> None:
#     """Test login error."""

#     with patch(
#         "homeassistant.components.airzone_cloud.AirzoneCloudApi.login",
#         side_effect=LoginError,
#     ):
#         result = await hass.config_entries.flow.async_init(
#             DOMAIN,
#             context={"source": SOURCE_USER},
#             data={
#                 CONF_USERNAME: CONFIG[CONF_USERNAME],
#                 CONF_PASSWORD: CONFIG[CONF_PASSWORD],
#             },
#         )

#         assert result["errors"] == {"base": "cannot_connect"}
