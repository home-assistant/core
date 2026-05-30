"""Test the config flow of the Scaleway Object Storage integration."""

from collections.abc import Mapping
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.scaleway_object_storage import exceptions
from homeassistant.components.scaleway_object_storage.config_flow import (
    ScalewayConfigFlow,
)
from homeassistant.components.scaleway_object_storage.const import (
    CONF_BUCKET,
    CONF_OBJECT_PREFIX,
    CONF_REGION,
    CONF_SECTION_CREDENTIALS,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_user_flow_happy_path(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, valid_config: Mapping[str, Any]
) -> None:
    """Test the happy path of the initial setup flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.scaleway_object_storage.helpers.check_connection",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            valid_config,
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == ScalewayConfigFlow._generate_title(valid_config)
    assert result["data"] == valid_config
    assert len(mock_setup_entry.mock_calls) == 1


async def test_abort_if_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    valid_config: Mapping[str, Any],
) -> None:
    """Test we abort if the account is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.scaleway_object_storage.helpers.check_connection",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            valid_config,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_abort_if_already_configured_no_prefix(
    hass: HomeAssistant,
    mock_config_entry_no_prefix: MockConfigEntry,
) -> None:
    """Test we abort if the account is already configured."""
    mock_config_entry_no_prefix.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.scaleway_object_storage.helpers.check_connection",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            dict(mock_config_entry_no_prefix.data),
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("patched_config_entry", "patched_value"),
    [
        (CONF_REGION, "nl-ams"),
        (CONF_BUCKET, "other-bucket"),
        (CONF_OBJECT_PREFIX, "other-prefix/"),
        (CONF_OBJECT_PREFIX, ""),
    ],
)
async def test_no_conflict_with_similar_configuration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    valid_config: Mapping[str, Any],
    patched_config_entry: str,
    patched_value: str | None,
) -> None:
    """Test that we can set up similar entries if the relevant fields change."""
    mock_config_entry.add_to_hass(hass)

    similar_config = dict(valid_config)
    if patched_value is None:
        del similar_config[patched_config_entry]
    else:
        similar_config[patched_config_entry] = patched_value

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.scaleway_object_storage.helpers.check_connection",
        return_value=None,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            similar_config,
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == ScalewayConfigFlow._generate_title(similar_config)
    assert result["data"] == similar_config


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
    valid_config: Mapping[str, Any],
    exception: Exception,
    error_schema_key: str,
    error_code: str,
) -> None:
    """Test we handle exceptions raised during connection check."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.scaleway_object_storage.helpers.check_connection",
        side_effect=exception,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            valid_config,
        )

    assert result["type"] is FlowResultType.FORM
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

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == ScalewayConfigFlow._generate_title(valid_config)
    assert result["data"] == valid_config
    assert len(mock_setup_entry.mock_calls) == 1
