"""Test the reauth step of the Scaleway Object Storage config flow."""

from collections.abc import Mapping
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.scaleway_object_storage import exceptions
from homeassistant.components.scaleway_object_storage.const import (
    CONF_ACCESS_KEY_ID,
    CONF_BUCKET,
    CONF_SECRET_KEY,
    CONF_SECTION_CREDENTIALS,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

type AuthConfig = Mapping[str, Mapping[str, str]]


@pytest.fixture
def updated_auth_config() -> AuthConfig:
    """The credentials section of our config with different values than in the default `valid_config` fixture."""
    return {
        CONF_SECTION_CREDENTIALS: {
            CONF_ACCESS_KEY_ID: "new_key_id",
            CONF_SECRET_KEY: "newsupersecret",
        }
    }


async def test_form(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    valid_config: Mapping[str, Any],
    updated_auth_config: AuthConfig,
) -> None:
    """Test we get the form."""
    title_pre_reconfigure = mock_config_entry.title
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] == FlowResultType.FORM
    assert {k.schema for k in result["data_schema"].schema} == {
        CONF_SECTION_CREDENTIALS
    }
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.scaleway_object_storage.helpers.check_connection",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            updated_auth_config,
        )
        await hass.async_block_till_done()

    expected_config = dict(valid_config)
    expected_config.update(updated_auth_config)

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.title == title_pre_reconfigure
    assert mock_config_entry.data == expected_config
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.parametrize(
    ("exception", "error_schema_key", "error_code"),
    [
        (exceptions.ScalewayConnectionError(), "base", "cannot_connect"),
        (exceptions.ServerUnavailableError(), "base", "server_unavailable"),
        (exceptions.UnsuccessfulResponseError(400), "base", "unsuccessful_response"),
        (exceptions.InvalidBucketNameException(), CONF_BUCKET, "invalid_bucket_name"),
        (exceptions.BucketNotFoundException(), CONF_BUCKET, "bucket_not_found"),
        (exceptions.InvalidAuthException(), CONF_SECTION_CREDENTIALS, "invalid_auth"),
    ],
)
async def test_form_failed_connection_check(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    valid_config: Mapping[str, Any],
    updated_auth_config: AuthConfig,
    exception: Exception,
    error_schema_key: str,
    error_code: str,
) -> None:
    """Test we handle exceptions raised during connection check."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)

    with patch(
        "homeassistant.components.scaleway_object_storage.helpers.check_connection",
        side_effect=exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            updated_auth_config,
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {error_schema_key: error_code}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.
    with patch(
        "homeassistant.components.scaleway_object_storage.helpers.check_connection",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            updated_auth_config,
        )
        await hass.async_block_till_done()

    expected_config = dict(valid_config)
    expected_config.update(updated_auth_config)

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.data == expected_config
    assert len(mock_setup_entry.mock_calls) == 1
