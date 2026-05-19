"""Test the ESPHome Dashboard config flow."""

from unittest.mock import AsyncMock, patch

import aiohttp

from homeassistant import config_entries
from homeassistant.components.esphome_dashboard.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_URL, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_user_flow_success(hass: HomeAssistant, mock_dashboard_api) -> None:
    """Test successful user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.esphome_dashboard.config_flow.ESPHomeDashboardAPI",
        return_value=mock_dashboard_api,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_URL: "http://192.168.1.100:6052"},
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["title"] == "ESPHome Dashboard (192.168.1.100:6052)"
    assert result["data"] == {CONF_URL: "http://192.168.1.100:6052"}


async def test_user_flow_invalid_url(hass: HomeAssistant) -> None:
    """Test user flow with invalid URL."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_URL: "not-a-valid-url"},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_url"}


async def test_user_flow_invalid_port(hass: HomeAssistant) -> None:
    """Test user flow with port number out of valid range."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    # Port number exceeds valid range (0-65535), triggers ValueError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_URL: "http://192.168.1.100:99999999"},
    )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_url"}


async def test_user_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test user flow when connection fails."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.esphome_dashboard.config_flow.ESPHomeDashboardAPI"
    ) as mock_api:
        mock_api.return_value.request = AsyncMock(
            side_effect=Exception("Connection error")
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_URL: "http://192.168.1.100:6052"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_invalid_dashboard(hass: HomeAssistant) -> None:
    """Test user flow when dashboard returns invalid data."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.esphome_dashboard.config_flow.ESPHomeDashboardAPI"
    ) as mock_api:
        mock_api.return_value.request = AsyncMock(return_value=None)
        mock_api.return_value.get_devices = AsyncMock(return_value={})

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_URL: "http://192.168.1.100:6052"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_dashboard"}


async def test_user_flow_already_configured(
    hass: HomeAssistant, mock_config_entry, mock_dashboard_api
) -> None:
    """Test user flow when dashboard is already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.esphome_dashboard.config_flow.ESPHomeDashboardAPI",
        return_value=mock_dashboard_api,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_URL: "http://192.168.1.100:6052"},
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_reconfigure_flow_success(
    hass: HomeAssistant, mock_config_entry, mock_dashboard_api
) -> None:
    """Test successful reconfigure flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    with patch(
        "homeassistant.components.esphome_dashboard.config_flow.ESPHomeDashboardAPI",
        return_value=mock_dashboard_api,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_URL: "http://192.168.1.200:6052"},
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_URL] == "http://192.168.1.200:6052"


async def test_reconfigure_flow_cannot_connect(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test reconfigure flow when connection fails."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        },
    )

    with patch(
        "homeassistant.components.esphome_dashboard.config_flow.ESPHomeDashboardAPI"
    ) as mock_api:
        mock_api.return_value.request = AsyncMock(
            side_effect=Exception("Connection error")
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_URL: "http://192.168.1.200:6052"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_with_authentication(
    hass: HomeAssistant, mock_dashboard_api
) -> None:
    """Test user flow with authentication credentials."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.esphome_dashboard.config_flow.ESPHomeDashboardAPI",
        return_value=mock_dashboard_api,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_URL: "http://192.168.1.100:6052",
                CONF_USERNAME: "admin",
                CONF_PASSWORD: "password",
            },
        )

    assert result["type"] == FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_URL] == "http://192.168.1.100:6052"
    assert result["data"][CONF_USERNAME] == "admin"
    assert result["data"][CONF_PASSWORD] == "password"


async def test_user_flow_invalid_authentication(hass: HomeAssistant) -> None:
    """Test user flow with invalid authentication credentials."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.esphome_dashboard.config_flow.ESPHomeDashboardAPI"
    ) as mock_api:
        mock_api.return_value.request = AsyncMock(
            side_effect=aiohttp.ClientResponseError(
                request_info=None, history=None, status=401
            )
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_URL: "http://192.168.1.100:6052",
                CONF_USERNAME: "admin",
                CONF_PASSWORD: "wrong_password",
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_reauth_flow_success(
    hass: HomeAssistant, mock_config_entry, mock_dashboard_api
) -> None:
    """Test successful reauth flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config_entry.entry_id,
        },
        data=mock_config_entry.data,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.esphome_dashboard.config_flow.ESPHomeDashboardAPI",
        return_value=mock_dashboard_api,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_USERNAME: "admin",
                CONF_PASSWORD: "new_password",
            },
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


async def test_reauth_flow_invalid_credentials(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Test reauth flow with invalid credentials."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config_entry.entry_id,
        },
        data=mock_config_entry.data,
    )

    with patch(
        "homeassistant.components.esphome_dashboard.config_flow.ESPHomeDashboardAPI"
    ) as mock_api:
        mock_api.return_value.request = AsyncMock(
            side_effect=aiohttp.ClientResponseError(
                request_info=None, history=None, status=401
            )
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_USERNAME: "admin",
                CONF_PASSWORD: "still_wrong",
            },
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_non_auth_http_error(hass: HomeAssistant) -> None:
    """Test user flow with non-authentication HTTP error (e.g., 500)."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.esphome_dashboard.config_flow.ESPHomeDashboardAPI"
    ) as mock_api:
        mock_api.return_value.request = AsyncMock(
            side_effect=aiohttp.ClientResponseError(
                request_info=None, history=None, status=500
            )
        )

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_URL: "http://192.168.1.100:6052"},
        )

    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_reconfigure_flow_with_authentication(
    hass: HomeAssistant, mock_config_entry, mock_dashboard_api
) -> None:
    """Test reconfigure flow adding authentication credentials."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        },
    )

    with patch(
        "homeassistant.components.esphome_dashboard.config_flow.ESPHomeDashboardAPI",
        return_value=mock_dashboard_api,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_URL: "http://192.168.1.200:6052",
                CONF_USERNAME: "admin",
                CONF_PASSWORD: "secret",
            },
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert mock_config_entry.data[CONF_URL] == "http://192.168.1.200:6052"
    assert mock_config_entry.data[CONF_USERNAME] == "admin"
    assert mock_config_entry.data[CONF_PASSWORD] == "secret"


async def test_reconfigure_flow_with_existing_credentials(
    hass: HomeAssistant, mock_dashboard_api
) -> None:
    """Test reconfigure flow shows existing credentials in form."""
    # Create entry with existing credentials
    entry = MockConfigEntry(
        title="ESPHome Dashboard (192.168.1.100:6052)",
        domain=DOMAIN,
        data={
            CONF_URL: "http://192.168.1.100:6052",
            CONF_USERNAME: "existing_user",
            CONF_PASSWORD: "existing_pass",
        },
        unique_id="http://192.168.1.100:6052",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
    )

    # The form should be shown with suggested values from existing data
    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reconfigure"

    # Now complete the reconfigure to a NEW URL without credentials to remove auth
    with patch(
        "homeassistant.components.esphome_dashboard.config_flow.ESPHomeDashboardAPI",
        return_value=mock_dashboard_api,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={CONF_URL: "http://192.168.1.200:6052"},  # Different URL
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    # Auth should be removed when not provided
    assert entry.data.get(CONF_USERNAME) is None
    assert entry.data.get(CONF_PASSWORD) is None
    assert entry.data[CONF_URL] == "http://192.168.1.200:6052"


async def test_reauth_flow_clear_credentials(
    hass: HomeAssistant, mock_dashboard_api
) -> None:
    """Test reauth flow can clear credentials by providing empty values."""
    # Create entry with existing credentials
    entry = MockConfigEntry(
        title="ESPHome Dashboard (192.168.1.100:6052)",
        domain=DOMAIN,
        data={
            CONF_URL: "http://192.168.1.100:6052",
            CONF_USERNAME: "old_user",
            CONF_PASSWORD: "old_pass",
        },
        unique_id="http://192.168.1.100:6052",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
        data=entry.data,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    # Submit without credentials to clear them
    with patch(
        "homeassistant.components.esphome_dashboard.config_flow.ESPHomeDashboardAPI",
        return_value=mock_dashboard_api,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={},  # Empty input clears credentials
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    # Credentials should be cleared
    assert entry.data.get(CONF_USERNAME) is None
    assert entry.data.get(CONF_PASSWORD) is None


async def test_reauth_flow_with_suggested_username(
    hass: HomeAssistant, mock_dashboard_api
) -> None:
    """Test reauth flow pre-fills username from existing config."""
    # Create entry with existing username
    entry = MockConfigEntry(
        title="ESPHome Dashboard (192.168.1.100:6052)",
        domain=DOMAIN,
        data={
            CONF_URL: "http://192.168.1.100:6052",
            CONF_USERNAME: "saved_user",
            CONF_PASSWORD: "saved_pass",
        },
        unique_id="http://192.168.1.100:6052",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
        data=entry.data,
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    # Submit new credentials
    with patch(
        "homeassistant.components.esphome_dashboard.config_flow.ESPHomeDashboardAPI",
        return_value=mock_dashboard_api,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            user_input={
                CONF_USERNAME: "new_user",
                CONF_PASSWORD: "new_pass",
            },
        )

    assert result["type"] == FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_USERNAME] == "new_user"
    assert entry.data[CONF_PASSWORD] == "new_pass"
