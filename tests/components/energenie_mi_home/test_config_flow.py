"""Test the energenie_mi_home config flow."""

from unittest.mock import AsyncMock, patch

from homeassistant import config_entries
from homeassistant.components.energenie_mi_home.config_flow import (
    CannotConnect,
    InvalidAuth,
)
from homeassistant.components.energenie_mi_home.const import DOMAIN
from homeassistant.const import CONF_API_KEY, CONF_EMAIL, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.energenie_mi_home.config_flow.MiHomeAPI",
            autospec=True,
        ) as mock_api_class,
        patch(
            "homeassistant.components.energenie_mi_home.config_flow.validate_input",
        ) as mock_validate,
    ):
        mock_api = mock_api_class.return_value
        mock_api.async_authenticate = AsyncMock(return_value="test-api-key")
        mock_api.async_get_devices = AsyncMock(return_value=[])
        mock_validate.return_value = {
            "title": "test@example.com",
            "user_id": "test@example.com",
            "api_key": "test-api-key",
        }

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "test@example.com",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test@example.com"
    assert result["data"] == {
        CONF_EMAIL: "test@example.com",
        CONF_PASSWORD: "test-password",
        CONF_API_KEY: "test-api-key",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.energenie_mi_home.config_flow.validate_input",
        side_effect=InvalidAuth,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "test@example.com",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.
    with (
        patch(
            "homeassistant.components.energenie_mi_home.config_flow.MiHomeAPI",
            autospec=True,
        ) as mock_api_class,
        patch(
            "homeassistant.components.energenie_mi_home.config_flow.validate_input",
        ) as mock_validate,
    ):
        mock_api = mock_api_class.return_value
        mock_api.async_authenticate = AsyncMock(return_value="test-api-key")
        mock_api.async_get_devices = AsyncMock(return_value=[])
        mock_validate.return_value = {
            "title": "test@example.com",
            "user_id": "test@example.com",
            "api_key": "test-api-key",
        }

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "test@example.com",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test@example.com"
    assert result["data"] == {
        CONF_EMAIL: "test@example.com",
        CONF_PASSWORD: "test-password",
        CONF_API_KEY: "test-api-key",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.energenie_mi_home.config_flow.validate_input",
        side_effect=CannotConnect,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "test@example.com",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    # Make sure the config flow tests finish with either an
    # FlowResultType.CREATE_ENTRY or FlowResultType.ABORT so
    # we can show the config flow is able to recover from an error.
    with (
        patch(
            "homeassistant.components.energenie_mi_home.config_flow.MiHomeAPI",
            autospec=True,
        ) as mock_api_class,
        patch(
            "homeassistant.components.energenie_mi_home.config_flow.validate_input",
        ) as mock_validate,
    ):
        mock_api = mock_api_class.return_value
        mock_api.async_authenticate = AsyncMock(return_value="test-api-key")
        mock_api.async_get_devices = AsyncMock(return_value=[])
        mock_validate.return_value = {
            "title": "test@example.com",
            "user_id": "test@example.com",
            "api_key": "test-api-key",
        }

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "test@example.com",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test@example.com"
    assert result["data"] == {
        CONF_EMAIL: "test@example.com",
        CONF_PASSWORD: "test-password",
        CONF_API_KEY: "test-api-key",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_duplicate_entry(hass: HomeAssistant) -> None:
    """Test that duplicate entries are prevented."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_EMAIL: "test@example.com", CONF_PASSWORD: "test-password"},
        unique_id="test@example.com",
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with (
        patch(
            "homeassistant.components.energenie_mi_home.config_flow.MiHomeAPI",
            autospec=True,
        ) as mock_api_class,
        patch(
            "homeassistant.components.energenie_mi_home.config_flow.validate_input",
        ) as mock_validate,
    ):
        mock_api = mock_api_class.return_value
        mock_api.async_authenticate = AsyncMock(return_value="test-api-key")
        mock_api.async_get_devices = AsyncMock(return_value=[])
        mock_validate.return_value = {
            "title": "test@example.com",
            "user_id": "test@example.com",
            "api_key": "test-api-key",
        }

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_EMAIL: "test@example.com",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
