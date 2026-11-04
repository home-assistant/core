"""Tests for the Amazon Polly config flow."""

from typing import Any
from unittest.mock import AsyncMock

from botocore.exceptions import ClientError, EndpointConnectionError
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.amazon_polly.const import (
    CONF_ACCESS_KEY_ID,
    CONF_ENGINE,
    CONF_OUTPUT_FORMAT,
    CONF_REGION,
    CONF_SAMPLE_RATE,
    CONF_SECRET_ACCESS_KEY,
    CONF_TEXT_TYPE,
    CONF_VOICE,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import ACCESS_KEY_ID, ENTRY_DATA, REGION, UNIQUE_ID

NEW_ACCESS_KEY_ID = "AKIAI44QH8DHBEXAMPLE"
NEW_SECRET_ACCESS_KEY = "je7MtGbClwBF/2Zp9Utk/h3yCo8nvbEXAMPLEKEY"

OPTIONS = {
    CONF_VOICE: "Amy",
    CONF_ENGINE: "neural",
    CONF_OUTPUT_FORMAT: "ogg_vorbis",
    CONF_SAMPLE_RATE: "16000",
    CONF_TEXT_TYPE: "ssml",
}

CONNECTION_ERRORS = [
    pytest.param(
        ClientError(
            {"Error": {"Code": "UnrecognizedClientException", "Message": "Bad key"}},
            "DescribeVoices",
        ),
        "invalid_auth",
        id="invalid_auth",
    ),
    pytest.param(
        ClientError(
            {"Error": {"Code": "ThrottlingException", "Message": "Slow down"}},
            "DescribeVoices",
        ),
        "cannot_connect",
        id="client_error",
    ),
    pytest.param(
        EndpointConnectionError(endpoint_url="https://polly.us-east-1.amazonaws.com"),
        "cannot_connect",
        id="cannot_connect",
    ),
    pytest.param(RuntimeError("boom"), "unknown", id="unknown"),
]


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow(hass: HomeAssistant, mock_polly_client: AsyncMock) -> None:
    """Test creating an entry from the UI."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], ENTRY_DATA
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Amazon Polly (us-east-1)"
    assert result["data"] == ENTRY_DATA
    assert result["result"].unique_id == UNIQUE_ID
    mock_polly_client.__aexit__.assert_awaited_once()


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(("side_effect", "error"), CONNECTION_ERRORS)
async def test_user_flow_errors(
    hass: HomeAssistant,
    mock_polly_client: AsyncMock,
    side_effect: Exception,
    error: str,
) -> None:
    """Test the user flow shows errors and recovers."""
    mock_polly_client.describe_voices.side_effect = side_effect
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], ENTRY_DATA
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}

    mock_polly_client.describe_voices.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], ENTRY_DATA
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_polly_client", "mock_setup_entry")
async def test_user_flow_invalid_region(hass: HomeAssistant) -> None:
    """Test a typed region Polly doesn't support is rejected and recovers."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], ENTRY_DATA | {CONF_REGION: "mars-north-1"}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_REGION: "invalid_region"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], ENTRY_DATA
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY


@pytest.mark.usefixtures("mock_polly_client", "mock_setup_entry")
async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test the same key and region can only be added once."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], ENTRY_DATA
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_polly_client", "mock_setup_entry")
async def test_import(hass: HomeAssistant) -> None:
    """Test importing a YAML configured platform."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=ENTRY_DATA | OPTIONS | {"platform": DOMAIN},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == ENTRY_DATA
    assert result["options"] == OPTIONS
    assert result["result"].unique_id == UNIQUE_ID


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(("side_effect", "reason"), CONNECTION_ERRORS)
async def test_import_errors(
    hass: HomeAssistant,
    mock_polly_client: AsyncMock,
    side_effect: Exception,
    reason: str,
) -> None:
    """Test a failing import aborts with the error."""
    mock_polly_client.describe_voices.side_effect = side_effect
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=ENTRY_DATA
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == reason


@pytest.mark.usefixtures("mock_polly_client")
@pytest.mark.parametrize(
    ("access_key_id", "unique_id"),
    [
        pytest.param(ACCESS_KEY_ID, UNIQUE_ID, id="same_key"),
        pytest.param(
            NEW_ACCESS_KEY_ID, f"{NEW_ACCESS_KEY_ID}_{REGION}", id="rotated_key"
        ),
    ],
)
async def test_reauth(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    access_key_id: str,
    unique_id: str,
) -> None:
    """Test reauthenticating with a new secret or a rotated key."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_ACCESS_KEY_ID: access_key_id,
            CONF_SECRET_ACCESS_KEY: NEW_SECRET_ACCESS_KEY,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert mock_config_entry.unique_id == unique_id
    assert mock_config_entry.title == "Amazon Polly (us-east-1)"
    assert mock_config_entry.data == {
        CONF_REGION: REGION,
        CONF_ACCESS_KEY_ID: access_key_id,
        CONF_SECRET_ACCESS_KEY: NEW_SECRET_ACCESS_KEY,
    }


async def test_reconfigure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_polly_client: AsyncMock,
) -> None:
    """Test moving an entry to another region, recovering from an error."""
    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reconfigure_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"
    user_input = ENTRY_DATA | {CONF_REGION: "eu-west-2"}

    mock_polly_client.describe_voices.side_effect = EndpointConnectionError(
        endpoint_url="https://polly.eu-west-2.amazonaws.com"
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    mock_polly_client.describe_voices.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.unique_id == f"{ACCESS_KEY_ID}_eu-west-2"
    assert mock_config_entry.title == "Amazon Polly (eu-west-2)"
    assert mock_config_entry.data[CONF_REGION] == "eu-west-2"


@pytest.mark.usefixtures("mock_polly_client")
async def test_options_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setting the default voice and audio options."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], OPTIONS
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert mock_config_entry.options == OPTIONS


@pytest.mark.usefixtures("mock_polly_client")
@pytest.mark.parametrize(
    ("user_input", "errors"),
    [
        pytest.param(
            OPTIONS | {CONF_OUTPUT_FORMAT: "pcm", CONF_SAMPLE_RATE: "24000"},
            {CONF_SAMPLE_RATE: "invalid_sample_rate"},
            id="invalid_sample_rate",
        ),
        pytest.param(
            OPTIONS | {CONF_VOICE: "Brian"},
            {CONF_ENGINE: "engine_not_supported"},
            id="engine_not_supported",
        ),
    ],
)
async def test_options_flow_errors(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    user_input: dict[str, Any],
    errors: dict[str, str],
) -> None:
    """Test invalid option combinations are rejected."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await hass.config_entries.options.async_init(mock_config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], user_input
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == errors

    result = await hass.config_entries.options.async_configure(
        result["flow_id"], OPTIONS
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
