"""Test the Wireless Sensor Tag config flow."""

from __future__ import annotations

from unittest.mock import Mock, patch

from wirelesstagpy.exceptions import WirelessTagsException

from homeassistant.components.wirelesstag.config_flow import validate_input
from homeassistant.components.wirelesstag.const import DOMAIN
from homeassistant.config_entries import SOURCE_REAUTH, SOURCE_USER
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

TEST_USER_INPUT = {
    CONF_USERNAME: "test@example.com",
    CONF_PASSWORD: "test_password",
}


async def test_user_flow_success(
    hass: HomeAssistant, mock_setup_entry: Mock, mock_wirelesstags_api: Mock
) -> None:
    """Test successful user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "user"
    assert result.get("errors", {}) == {}

    with patch(
        "homeassistant.components.wirelesstag.config_flow.WirelessTags"
    ) as mock_api:
        mock_api.return_value = mock_wirelesstags_api

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=TEST_USER_INPUT
        )

    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert result.get("title") == "Wireless Sensor Tags"
    assert result.get("data") == TEST_USER_INPUT
    assert len(mock_setup_entry.mock_calls) == 1


async def test_user_flow_invalid_auth(
    hass: HomeAssistant, mock_setup_entry: Mock
) -> None:
    """Test user flow with invalid authentication."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "user"

    with patch(
        "homeassistant.components.wirelesstag.config_flow.WirelessTags"
    ) as mock_api:
        mock_api.side_effect = WirelessTagsException("Invalid credentials")

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=TEST_USER_INPUT
        )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "user"
    errors = result.get("errors") or {}
    assert errors.get("base") == "invalid_auth"
    assert len(mock_setup_entry.mock_calls) == 0


async def test_user_flow_connection_error(
    hass: HomeAssistant, mock_setup_entry: Mock
) -> None:
    """Test user flow with connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "user"

    with patch(
        "homeassistant.components.wirelesstag.config_flow.WirelessTags"
    ) as mock_api:
        mock_api.side_effect = ConnectionError("Connection timeout")

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=TEST_USER_INPUT
        )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "user"
    errors = result.get("errors") or {}
    assert errors.get("base") == "unknown"
    assert len(mock_setup_entry.mock_calls) == 0


async def test_user_flow_unknown_error(
    hass: HomeAssistant, mock_setup_entry: Mock
) -> None:
    """Test user flow with unknown error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "user"

    with patch(
        "homeassistant.components.wirelesstag.config_flow.WirelessTags"
    ) as mock_api:
        mock_api.side_effect = Exception("Unexpected error")

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=TEST_USER_INPUT
        )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "user"
    errors = result.get("errors") or {}
    assert errors.get("base") == "unknown"
    assert len(mock_setup_entry.mock_calls) == 0


async def test_user_flow_duplicate_prevention(
    hass: HomeAssistant, mock_setup_entry: Mock, mock_wirelesstags_api: Mock
) -> None:
    """Test user flow prevents duplicate entries."""
    # Create existing entry
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test@example.com",
        data=TEST_USER_INPUT,
    )
    existing_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "user"

    with patch(
        "homeassistant.components.wirelesstag.config_flow.WirelessTags"
    ) as mock_api:
        mock_api.return_value = mock_wirelesstags_api

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=TEST_USER_INPUT
        )

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "already_configured"
    assert len(mock_setup_entry.mock_calls) == 0


async def test_reauth_flow_success(
    hass: HomeAssistant, mock_setup_entry: Mock, mock_wirelesstags_api: Mock
) -> None:
    """Test successful reauth flow."""
    # Create existing entry
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test@example.com",
        data=TEST_USER_INPUT,
    )
    existing_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": existing_entry.entry_id},
        data=existing_entry.data,
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "reauth_confirm"

    new_data = {
        CONF_USERNAME: "test@example.com",
        CONF_PASSWORD: "new_password",
    }

    with patch(
        "homeassistant.components.wirelesstag.config_flow.validate_input"
    ) as mock_validate:
        mock_validate.return_value = {"title": "Wireless Sensor Tags", "tags_count": 2}

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=new_data
        )

    assert result.get("type") == FlowResultType.ABORT
    assert result.get("reason") == "reauth_successful"
    assert existing_entry.data == new_data


async def test_reauth_flow_invalid_auth(
    hass: HomeAssistant, mock_setup_entry: Mock
) -> None:
    """Test reauth flow with invalid authentication."""
    # Create existing entry
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test@example.com",
        data=TEST_USER_INPUT,
    )
    existing_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": existing_entry.entry_id},
        data=existing_entry.data,
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "reauth_confirm"

    new_data = {
        CONF_USERNAME: "test@example.com",
        CONF_PASSWORD: "wrong_password",
    }

    with patch(
        "homeassistant.components.wirelesstag.config_flow.validate_input"
    ) as mock_validate:
        mock_validate.side_effect = WirelessTagsException("Invalid credentials")

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=new_data
        )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "reauth_confirm"
    errors = result.get("errors") or {}
    assert errors.get("base") == "invalid_auth"


async def test_reauth_flow_unknown_error(
    hass: HomeAssistant, mock_setup_entry: Mock
) -> None:
    """Test reauth flow with unknown error."""
    # Create existing entry
    existing_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="test@example.com",
        data=TEST_USER_INPUT,
    )
    existing_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_REAUTH, "entry_id": existing_entry.entry_id},
        data=existing_entry.data,
    )
    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "reauth_confirm"

    new_data = {
        CONF_USERNAME: "test@example.com",
        CONF_PASSWORD: "new_password",
    }

    with patch(
        "homeassistant.components.wirelesstag.config_flow.validate_input"
    ) as mock_validate:
        mock_validate.side_effect = Exception("Unexpected error")

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=new_data
        )

    assert result.get("type") == FlowResultType.FORM
    assert result.get("step_id") == "reauth_confirm"
    errors = result.get("errors") or {}
    assert errors.get("base") == "unknown"


async def test_validate_input_function(mock_wirelesstags_api: Mock) -> None:
    """Test the validate_input helper function."""
    hass = HomeAssistant("/test")

    with patch(
        "homeassistant.components.wirelesstag.config_flow.WirelessTags"
    ) as mock_api:
        mock_api.return_value = mock_wirelesstags_api

        result = await validate_input(hass, TEST_USER_INPUT)

    assert result.get("title") == "Wireless Sensor Tags"
    assert "tags_count" in result
    mock_api.assert_called_once_with("test@example.com", "test_password")
    mock_wirelesstags_api.load_tags.assert_called_once()
