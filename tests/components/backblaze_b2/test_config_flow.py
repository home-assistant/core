"""Test the Backblaze B2 config flow."""

from unittest.mock import patch

from b2sdk.v2 import exception

from homeassistant import config_entries
from homeassistant.components.backblaze_b2.const import (
    CONF_APPLICATION_KEY,
    CONF_KEY_ID,
    DOMAIN,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import BackblazeFixture
from .const import USER_INPUT

from tests.common import MockConfigEntry


async def _async_start_flow(
    hass: HomeAssistant,
    key_id: str,
    application_key: str,
    user_input: dict[str, str] | None = None,
) -> config_entries.ConfigFlowResult:
    """Initialize the config flow."""
    if user_input is None:
        user_input = USER_INPUT

    user_input[CONF_KEY_ID] = key_id
    user_input[CONF_APPLICATION_KEY] = application_key
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") is FlowResultType.FORM

    return await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input,
    )


async def test_flow(hass: HomeAssistant, b2_fixture: BackblazeFixture) -> None:
    """Test config flow."""
    result = await _async_start_flow(
        hass, b2_fixture.key_id, b2_fixture.application_key
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert result.get("title") == "testBucket"
    assert result.get("data") == USER_INPUT


async def test_abort_if_already_configured(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    b2_fixture: BackblazeFixture,
) -> None:
    """Test we abort if the account is already configured."""
    mock_config_entry.add_to_hass(hass)
    result = await _async_start_flow(
        hass, b2_fixture.key_id, b2_fixture.application_key
    )
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test config flow."""
    result = await _async_start_flow(hass, "invalid", "invalid")
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {"base": "invalid_credentials"}


async def test_form_invalid_bucket_name(
    hass: HomeAssistant,
    b2_fixture: BackblazeFixture,
) -> None:
    """Test config flow."""
    result = await _async_start_flow(
        hass,
        b2_fixture.key_id,
        b2_fixture.application_key,
        {
            **USER_INPUT,
            "bucket": "invalid-bucket-name",
        },
    )
    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {"bucket": "invalid_bucket_name"}


async def test_form_cannot_connect(
    hass: HomeAssistant,
    b2_fixture: BackblazeFixture,
) -> None:
    """Test config flow."""
    with patch(
        "b2sdk.v2.RawSimulator.authorize_account",
        side_effect=exception.ConnectionReset("test"),
    ):
        result = await _async_start_flow(
            hass,
            b2_fixture.key_id,
            b2_fixture.application_key,
            USER_INPUT,
        )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {"base": "cannot_connect"}


async def test_form_restricted_bucket(
    hass: HomeAssistant,
    b2_fixture: BackblazeFixture,
) -> None:
    """Test config flow."""
    with patch(
        "b2sdk.v2.RawSimulator.get_bucket_by_name",
        side_effect=exception.RestrictedBucket("testBucket"),
    ):
        result = await _async_start_flow(
            hass,
            b2_fixture.key_id,
            b2_fixture.application_key,
            USER_INPUT,
        )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {"bucket": "restricted_bucket"}
    assert result.get("description_placeholders") == {
        "restricted_bucket_name": "testBucket",
    }


async def test_form_missing_account_data(
    hass: HomeAssistant,
    b2_fixture: BackblazeFixture,
) -> None:
    """Test config flow."""
    with patch(
        "b2sdk.v2.RawSimulator.authorize_account",
        side_effect=exception.MissingAccountData("key"),
    ):
        result = await _async_start_flow(
            hass,
            b2_fixture.key_id,
            b2_fixture.application_key,
            USER_INPUT,
        )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {"base": "invalid_credentials"}


async def test_form_invalid_capability(
    hass: HomeAssistant,
    b2_fixture: BackblazeFixture,
) -> None:
    """Test config flow."""
    with patch(
        "b2sdk.v2.RawSimulator.account_info.get_allowed",
        return_value={
            "capabilities": [
                "writeFiles",
                "listFiles",
                "deleteFiles",
            ]
        },
    ):
        result = await _async_start_flow(
            hass,
            b2_fixture.key_id,
            b2_fixture.application_key,
            USER_INPUT,
        )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {"base": "invalid_capability"}


async def test_form_invalid_prefix(
    hass: HomeAssistant,
    b2_fixture: BackblazeFixture,
) -> None:
    """Test config flow."""
    with patch(
        "b2sdk.v2.RawSimulator.account_info.get_allowed",
        return_value={
            "capabilities": [
                "writeFiles",
                "listFiles",
                "deleteFiles",
                "readFiles",
            ],
            "namePrefix": "test/",
        },
    ):
        result = await _async_start_flow(
            hass,
            b2_fixture.key_id,
            b2_fixture.application_key,
            USER_INPUT,
        )

    assert result.get("type") is FlowResultType.FORM
    assert result.get("errors") == {"prefix": "invalid_prefix"}
    assert result.get("description_placeholders") == {
        "allowed_prefix": "test/",
    }
