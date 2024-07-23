"""Test the Aladdin Connect config flow."""

from unittest.mock import MagicMock, patch

from AIOAladdinConnect.session_manager import InvalidPasswordError
from aiohttp.client_exceptions import ClientConnectionError

from homeassistant import config_entries
from homeassistant.components.aladdin_connect.const import DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry


async def test_form(hass: HomeAssistant, mock_aladdinconnect_api: MagicMock) -> None:
    """Test we get the form."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None

    with (
        patch(
            "homeassistant.components.aladdin_connect.config_flow.AladdinConnectClient",
            return_value=mock_aladdinconnect_api,
        ),
        patch(
            "homeassistant.components.aladdin_connect.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Aladdin Connect"
    assert result2["data"] == {
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "test-password",
    }

    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_failed_auth(
    hass: HomeAssistant, mock_aladdinconnect_api: MagicMock
) -> None:
    """Test we handle failed authentication error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mock_aladdinconnect_api.login.return_value = False
    mock_aladdinconnect_api.login.side_effect = InvalidPasswordError
    with patch(
        "homeassistant.components.aladdin_connect.config_flow.AladdinConnectClient",
        return_value=mock_aladdinconnect_api,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_connection_timeout(
    hass: HomeAssistant, mock_aladdinconnect_api: MagicMock
) -> None:
    """Test we handle http timeout error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    mock_aladdinconnect_api.login.side_effect = ClientConnectionError
    with patch(
        "homeassistant.components.aladdin_connect.config_flow.AladdinConnectClient",
        return_value=mock_aladdinconnect_api,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_already_configured(
    hass: HomeAssistant, mock_aladdinconnect_api: MagicMock
) -> None:
    """Test we handle already configured error."""
    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_USERNAME: "test-username", CONF_PASSWORD: "test-password"},
        unique_id="test-username",
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == config_entries.SOURCE_USER

    with patch(
        "homeassistant.components.aladdin_connect.config_flow.AladdinConnectClient",
        return_value=mock_aladdinconnect_api,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: "test-username",
                CONF_PASSWORD: "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "already_configured"


async def test_reauth_flow(
    hass: HomeAssistant, mock_aladdinconnect_api: MagicMock
) -> None:
    """Test a successful reauth flow."""

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"username": "test-username", "password": "test-password"},
        unique_id="test-username",
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "unique_id": mock_entry.unique_id,
            "entry_id": mock_entry.entry_id,
        },
        data={"username": "test-username", "password": "new-password"},
    )

    assert result["step_id"] == "reauth_confirm"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with (
        patch(
            "homeassistant.components.aladdin_connect.async_setup_entry",
            return_value=True,
        ),
        patch(
            "homeassistant.components.aladdin_connect.config_flow.AladdinConnectClient",
            return_value=mock_aladdinconnect_api,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "new-password"},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert mock_entry.data == {
        CONF_USERNAME: "test-username",
        CONF_PASSWORD: "new-password",
    }


async def test_reauth_flow_auth_error(
    hass: HomeAssistant, mock_aladdinconnect_api: MagicMock
) -> None:
    """Test an authorization error reauth flow."""

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"username": "test-username", "password": "test-password"},
        unique_id="test-username",
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "unique_id": mock_entry.unique_id,
            "entry_id": mock_entry.entry_id,
        },
        data={"username": "test-username", "password": "new-password"},
    )

    assert result["step_id"] == "reauth_confirm"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    mock_aladdinconnect_api.login.return_value = False
    mock_aladdinconnect_api.login.side_effect = InvalidPasswordError
    with (
        patch(
            "homeassistant.components.aladdin_connect.config_flow.AladdinConnectClient",
            return_value=mock_aladdinconnect_api,
        ),
        patch(
            "homeassistant.components.aladdin_connect.cover.async_setup_entry",
            return_value=True,
        ),
        patch(
            "homeassistant.components.aladdin_connect.cover.async_setup_entry",
            return_value=True,
        ),
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "new-password"},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_reauth_flow_connnection_error(
    hass: HomeAssistant, mock_aladdinconnect_api: MagicMock
) -> None:
    """Test a connection error reauth flow."""

    mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={"username": "test-username", "password": "test-password"},
        unique_id="test-username",
    )
    mock_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "unique_id": mock_entry.unique_id,
            "entry_id": mock_entry.entry_id,
        },
        data={"username": "test-username", "password": "new-password"},
    )

    assert result["step_id"] == "reauth_confirm"
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}
    mock_aladdinconnect_api.login.side_effect = ClientConnectionError

    with patch(
        "homeassistant.components.aladdin_connect.config_flow.AladdinConnectClient",
        return_value=mock_aladdinconnect_api,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_PASSWORD: "new-password"},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}
