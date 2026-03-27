"""Test the reconfigure step of the Scaleway Object Storage config flow."""

from collections.abc import Mapping
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.scaleway_object_storage import exceptions
from homeassistant.components.scaleway_object_storage.const import (
    CONF_BUCKET,
    CONF_OBJECT_PREFIX,
    CONF_REGION,
    CONF_SECTION_CREDENTIALS,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    valid_config: Mapping[str, Any],
) -> None:
    """Test we get the form."""
    title_pre_reconfigure = mock_config_entry.title
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    config = dict(valid_config)
    config[CONF_OBJECT_PREFIX] = "reconfigured-prefix/"

    with patch(
        "homeassistant.components.scaleway_object_storage.helpers.check_connection",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            config,
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.title == title_pre_reconfigure
    assert mock_config_entry.data == config
    assert len(mock_setup_entry.mock_calls) == 1


async def test_abort_if_already_configured(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_config_entry: MockConfigEntry,
    valid_config: Mapping[str, Any],
) -> None:
    """Test we abort if the account is already configured."""
    # Add a default entry to hass
    mock_config_entry.add_to_hass(hass)

    # Add a different entry to hass
    other_config = dict(valid_config)
    other_config[CONF_REGION] = "nl-ams"
    other_mock_config_entry = MockConfigEntry(
        # We pretend the user customized the title to ensure the title isn't overwritten by defaults
        title="other-entry",
        domain=DOMAIN,
        data=other_config,
    )
    other_mock_config_entry.add_to_hass(hass)

    # Now start a reconfigure flow and try to change the second entry to match the first
    result = await other_mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.scaleway_object_storage.helpers.check_connection",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            valid_config,
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


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
    exception: Exception,
    error_schema_key: str,
    error_code: str,
) -> None:
    """Test we handle exceptions raised during connection check."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)

    with patch(
        "homeassistant.components.scaleway_object_storage.helpers.check_connection",
        side_effect=exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            valid_config,
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
            valid_config,
        )
        await hass.async_block_till_done()

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data == valid_config
    assert len(mock_setup_entry.mock_calls) == 1
