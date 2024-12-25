"""Configuration flow tests for the Backblaze B2 integration."""

from unittest.mock import MagicMock

from b2sdk.v2.exception import InvalidAuthToken
import pytest

from homeassistant.components.backblaze.const import (
    CONF_APPLICATION_KEY,
    CONF_APPLICATION_KEY_ID,
    CONF_BUCKET,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


@pytest.mark.usefixtures("mock_backblaze")
async def test_user_flow(hass: HomeAssistant) -> None:
    """Test the full happy path user flow from start to finish."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_APPLICATION_KEY: "secret",
            CONF_APPLICATION_KEY_ID: "keyid",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "bucket"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_BUCKET: "bucket"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY

    config_entry = result["result"]
    assert config_entry.unique_id == "bucket"
    assert config_entry.data == {
        CONF_APPLICATION_KEY_ID: "keyid",
        CONF_APPLICATION_KEY: "secret",
        CONF_BUCKET: "bucket",
    }
    assert not config_entry.options


@pytest.mark.parametrize(
    ("side_effect", "expected_error"),
    [
        (InvalidAuthToken("back", "up"), {"base": "invalid_auth"}),
        (Exception, {"base": "unknown"}),
    ],
)
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_backblaze: MagicMock,
    side_effect: Exception,
    expected_error: dict[str, str],
) -> None:
    """Test we show user form on an error."""
    mock_backblaze.list_buckets.side_effect = side_effect

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_APPLICATION_KEY: "secret",
            CONF_APPLICATION_KEY_ID: "keyid",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == expected_error

    mock_backblaze.list_buckets.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_APPLICATION_KEY: "secret",
            CONF_APPLICATION_KEY_ID: "keyid",
        },
    )

    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_BUCKET: "bucket",
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY

    config_entry = result["result"]
    assert config_entry.unique_id == "bucket"
    assert config_entry.data == {
        CONF_APPLICATION_KEY_ID: "keyid",
        CONF_APPLICATION_KEY: "secret",
        CONF_BUCKET: "bucket",
    }
    assert not config_entry.options


@pytest.mark.usefixtures("mock_backblaze")
async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test configuration flow aborts when the bucket is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_APPLICATION_KEY: "secret",
            CONF_APPLICATION_KEY_ID: "keyid",
        },
    )

    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_BUCKET: "bucket",
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
