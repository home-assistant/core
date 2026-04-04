"""Tests for the luci config flow."""

from unittest.mock import MagicMock, patch

from homeassistant.components.luci.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

USER_INPUT = {
    CONF_HOST: "192.168.1.1",
    CONF_USERNAME: "root",
    CONF_PASSWORD: "password",
    CONF_SSL: False,
    CONF_VERIFY_SSL: True,
}


async def test_user_flow_success(
    hass: HomeAssistant, mock_luci_client: MagicMock
) -> None:
    """Test successful user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.luci.config_flow._try_connect",
    ) as mock_connect:
        mock_router = MagicMock()
        mock_router.is_logged_in.return_value = True
        mock_connect.return_value = mock_router

        with patch(
            "homeassistant.components.luci.OpenWrtRpc",
            return_value=mock_luci_client,
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input=USER_INPUT
            )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "192.168.1.1"
    assert result["data"] == USER_INPUT


async def test_user_flow_cannot_connect(hass: HomeAssistant) -> None:
    """Test connection error in user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.luci.config_flow._try_connect",
        side_effect=ConnectionError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=USER_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}


async def test_user_flow_invalid_auth(hass: HomeAssistant) -> None:
    """Test invalid auth in user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.luci.config_flow._try_connect",
    ) as mock_connect:
        mock_router = MagicMock()
        mock_router.is_logged_in.return_value = False
        mock_connect.return_value = mock_router

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=USER_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_user_flow_already_configured(hass: HomeAssistant) -> None:
    """Test we abort if already configured."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=USER_INPUT,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=USER_INPUT
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_recover_after_error(
    hass: HomeAssistant, mock_luci_client: MagicMock
) -> None:
    """Test recovery after a connection error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    with patch(
        "homeassistant.components.luci.config_flow._try_connect",
        side_effect=ConnectionError,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], user_input=USER_INPUT
        )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}

    with patch(
        "homeassistant.components.luci.config_flow._try_connect",
    ) as mock_connect:
        mock_router = MagicMock()
        mock_router.is_logged_in.return_value = True
        mock_connect.return_value = mock_router

        with patch(
            "homeassistant.components.luci.OpenWrtRpc",
            return_value=mock_luci_client,
        ):
            result = await hass.config_entries.flow.async_configure(
                result["flow_id"], user_input=USER_INPUT
            )

    assert result["type"] is FlowResultType.CREATE_ENTRY
