"""Configuration flow tests for the S3 integration."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components.s3backup.const import (
    CONF_ACCESS_KEY,
    CONF_BUCKET,
    CONF_S3_URL,
    CONF_SECRET_KEY,
    DOMAIN,
    LOGGER,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


@pytest.mark.usefixtures("mock_s3backup")
async def test_user_flow(hass: HomeAssistant) -> None:
    """Test the full happy path user flow from start to finish."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    LOGGER.info("Result: %s", result)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_SECRET_KEY: "secret",
            CONF_ACCESS_KEY: "keyid",
            CONF_S3_URL: "http://example.com",
        },
    )
    LOGGER.info("Result: %s", result)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bucket"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_BUCKET: "my-bucket"},
    )
    LOGGER.info("Result: %s", result)

    assert result["type"] is FlowResultType.CREATE_ENTRY

    config_entry = result["result"]
    assert config_entry.unique_id == "my-bucket"
    assert config_entry.data == {
        CONF_ACCESS_KEY: "keyid",
        CONF_SECRET_KEY: "secret",
        CONF_S3_URL: "http://example.com",
        CONF_BUCKET: "my-bucket",
    }
    assert not config_entry.options


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (Exception, {"base": "unknown"}),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_s3backup: MagicMock,
    side_effect: Exception,
    expected_error: dict[str, str],
) -> None:
    """Test we show user form on an error."""
    mock_s3backup.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_SECRET_KEY: "secret",
            CONF_ACCESS_KEY: "keyid",
            CONF_S3_URL: "http://example.com",
        },
    )

    LOGGER.info("Result: %s", result)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == expected_error

    mock_s3backup.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_SECRET_KEY: "secret",
            CONF_ACCESS_KEY: "keyid",
            CONF_S3_URL: "http://example.com",
        },
    )

    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_BUCKET: "my-bucket",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY

    config_entry = result["result"]
    assert config_entry.unique_id == "my-bucket"
    assert config_entry.data == {
        CONF_ACCESS_KEY: "keyid",
        CONF_SECRET_KEY: "secret",
        CONF_S3_URL: "http://example.com",
        CONF_BUCKET: "my-bucket",
    }
    assert not config_entry.options


@pytest.mark.usefixtures("mock_s3backup")
async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test configuration flow aborts when the bucket is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_SECRET_KEY: "secret",
            CONF_ACCESS_KEY: "keyid",
            CONF_S3_URL: "http://example.com",
        },
    )

    LOGGER.info("Result: %s", result)

    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_BUCKET: "my-bucket",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
