"""Test Autoskope config flow."""

from unittest.mock import AsyncMock, patch

from autoskope_client.models import CannotConnect, InvalidAuth

from homeassistant import config_entries
from homeassistant.components.autoskope.const import DEFAULT_HOST, DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}


async def test_form_success(hass: HomeAssistant, mock_autoskope_api: AsyncMock) -> None:
    """Test successful form submission."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.autoskope.config_flow.AutoskopeApi"
    ) as mock_api_class:
        mock_api_class.return_value = mock_autoskope_api

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test_user",
                CONF_PASSWORD: "test_password",
                CONF_HOST: DEFAULT_HOST,
            },
        )
        await hass.async_block_till_done()

        assert result2["type"] is FlowResultType.CREATE_ENTRY
        assert result2["title"] == "Autoskope test_user"
        assert result2["data"] == {
            CONF_USERNAME: "test_user",
            CONF_PASSWORD: "test_password",
            CONF_HOST: DEFAULT_HOST,
        }


async def test_form_invalid_auth(
    hass: HomeAssistant, mock_autoskope_api: AsyncMock
) -> None:
    """Test form with invalid authentication."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_autoskope_api.authenticate.side_effect = InvalidAuth("Invalid credentials")

    with patch(
        "homeassistant.components.autoskope.config_flow.AutoskopeApi"
    ) as mock_api_class:
        mock_api_class.return_value = mock_autoskope_api

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test_user",
                CONF_PASSWORD: "wrong_password",
                CONF_HOST: DEFAULT_HOST,
            },
        )

        assert result2["type"] is FlowResultType.FORM
        assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(
    hass: HomeAssistant, mock_autoskope_api: AsyncMock
) -> None:
    """Test form with connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_autoskope_api.authenticate.side_effect = CannotConnect("Connection failed")

    with patch(
        "homeassistant.components.autoskope.config_flow.AutoskopeApi"
    ) as mock_api_class:
        mock_api_class.return_value = mock_autoskope_api

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test_user",
                CONF_PASSWORD: "test_password",
                CONF_HOST: "http://unreachable.host",
            },
        )

        assert result2["type"] is FlowResultType.FORM
        assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unexpected_error(
    hass: HomeAssistant, mock_autoskope_api: AsyncMock
) -> None:
    """Test form with unexpected error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_autoskope_api.authenticate.side_effect = Exception("Unexpected error")

    with patch(
        "homeassistant.components.autoskope.config_flow.AutoskopeApi"
    ) as mock_api_class:
        mock_api_class.return_value = mock_autoskope_api

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test_user",
                CONF_PASSWORD: "test_password",
                CONF_HOST: DEFAULT_HOST,
            },
        )

        assert result2["type"] is FlowResultType.FORM
        assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_already_configured(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test form with existing configuration."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.autoskope.config_flow.AutoskopeApi"
    ) as mock_api_class:
        mock_api_instance = AsyncMock()
        mock_api_instance.authenticate.return_value = True
        mock_api_class.return_value = mock_api_instance

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test_user",  # Same as in mock_config_entry
                CONF_PASSWORD: "test_password",
                CONF_HOST: DEFAULT_HOST,
            },
        )

        assert result2["type"] is FlowResultType.ABORT
        assert result2["reason"] == "already_configured"


async def test_reauth_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reauth flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config_entry.entry_id,
        },
        data=mock_config_entry.data,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"


async def test_reauth_flow_success(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
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

    with patch(
        "homeassistant.components.autoskope.config_flow.AutoskopeApi"
    ) as mock_api_class:
        mock_api_instance = AsyncMock()
        mock_api_instance.authenticate.return_value = True
        mock_api_class.return_value = mock_api_instance

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "new_password"},
        )

        assert result2["type"] is FlowResultType.ABORT
        assert result2["reason"] == "reauth_successful"


async def test_reauth_flow_invalid_auth(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reauth flow with invalid authentication."""
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
        "homeassistant.components.autoskope.config_flow.AutoskopeApi"
    ) as mock_api_class:
        mock_api_instance = AsyncMock()
        mock_api_instance.authenticate.side_effect = InvalidAuth("Invalid credentials")
        mock_api_class.return_value = mock_api_instance

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "wrong_password"},
        )

        assert result2["type"] is FlowResultType.FORM
        assert result2["errors"] == {"base": "invalid_auth"}


async def test_reconfigure_flow(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test reconfigure flow."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": mock_config_entry.entry_id,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reconfigure"


async def test_reconfigure_flow_success(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
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

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},  # No changes made (information only)
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reconfigure_successful"


async def test_form_with_custom_host(
    hass: HomeAssistant, mock_autoskope_api: AsyncMock
) -> None:
    """Test form with custom host."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.autoskope.config_flow.AutoskopeApi"
    ) as mock_api_class:
        mock_api_class.return_value = mock_autoskope_api

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test_user",
                CONF_PASSWORD: "test_password",
                CONF_HOST: "https://custom.autoskope.server",
            },
        )

        assert result2["type"] is FlowResultType.CREATE_ENTRY
        assert result2["data"][CONF_HOST] == "https://custom.autoskope.server"

        # Verify API was called with custom host
        mock_api_class.assert_called_with(
            host="https://custom.autoskope.server",
            username="test_user",
            password="test_password",
        )


async def test_form_auth_returns_false(
    hass: HomeAssistant, mock_autoskope_api: AsyncMock
) -> None:
    """Test form when authentication returns False."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_autoskope_api.authenticate.return_value = False

    with patch(
        "homeassistant.components.autoskope.config_flow.AutoskopeApi"
    ) as mock_api_class:
        mock_api_class.return_value = mock_autoskope_api

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test_user",
                CONF_PASSWORD: "test_password",
                CONF_HOST: DEFAULT_HOST,
            },
        )

        assert result2["type"] is FlowResultType.FORM
        assert result2["errors"] == {"base": "invalid_auth"}
