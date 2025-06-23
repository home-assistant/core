"""Test the NASweb config flow."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from webio_api.api_client import AuthError

from homeassistant import config_entries
from homeassistant.components.nasweb.const import DOMAIN
from homeassistant.config_entries import ConfigFlowResult
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.network import NoURLAvailableError

from .conftest import (
    BASE_CONFIG_FLOW,
    BASE_COORDINATOR,
    BASE_NASWEB_DATA,
    TEST_SERIAL_NUMBER,
)

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


TEST_USER_INPUT = {
    CONF_HOST: "1.1.1.1",
    CONF_USERNAME: "test-username",
    CONF_PASSWORD: "test-password",
}


async def _add_test_config_entry(hass: HomeAssistant) -> ConfigFlowResult:
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result.get("type") == FlowResultType.FORM
    assert not result.get("errors")

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], TEST_USER_INPUT
    )
    await hass.async_block_till_done()
    return result2


async def test_form(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    validate_input_all_ok: dict[str, AsyncMock | MagicMock],
) -> None:
    """Test the form."""
    result = await _add_test_config_entry(hass)

    assert result.get("type") == FlowResultType.CREATE_ENTRY
    assert result.get("title") == "1.1.1.1"
    assert result.get("data") == TEST_USER_INPUT

    config_entry = result.get("result")
    assert config_entry is not None
    assert config_entry.unique_id == TEST_SERIAL_NUMBER
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_cannot_connect(
    hass: HomeAssistant,
    validate_input_all_ok: dict[str, AsyncMock | MagicMock],
) -> None:
    """Test cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(BASE_CONFIG_FLOW + "WebioAPI.check_connection", return_value=False):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_USER_INPUT
        )

    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("errors") == {"base": "cannot_connect"}


async def test_form_invalid_auth(
    hass: HomeAssistant,
    validate_input_all_ok: dict[str, AsyncMock | MagicMock],
) -> None:
    """Test invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        BASE_CONFIG_FLOW + "WebioAPI.refresh_device_info",
        side_effect=AuthError,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_USER_INPUT
        )

    assert result2.get("type") == FlowResultType.FORM
    assert result2.get("errors") == {"base": "invalid_auth"}


async def test_form_missing_internal_url(
    hass: HomeAssistant,
    validate_input_all_ok: dict[str, AsyncMock | MagicMock],
) -> None:
    """Test missing internal url."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        BASE_NASWEB_DATA + "NASwebData.get_webhook_url", side_effect=NoURLAvailableError
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_USER_INPUT
        )
        assert result2.get("type") == FlowResultType.FORM
        assert result2.get("errors") == {"base": "missing_internal_url"}


async def test_form_missing_nasweb_data(
    hass: HomeAssistant,
    validate_input_all_ok: dict[str, AsyncMock | MagicMock],
) -> None:
    """Test invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        BASE_CONFIG_FLOW + "WebioAPI.get_serial_number",
        return_value=None,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_USER_INPUT
        )
        assert result2.get("type") == FlowResultType.FORM
        assert result2.get("errors") == {"base": "missing_nasweb_data"}
    with patch(BASE_CONFIG_FLOW + "WebioAPI.status_subscription", return_value=False):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_USER_INPUT
        )
        assert result2.get("type") == FlowResultType.FORM
        assert result2.get("errors") == {"base": "missing_nasweb_data"}


async def test_missing_status(
    hass: HomeAssistant,
    validate_input_all_ok: dict[str, AsyncMock | MagicMock],
) -> None:
    """Test missing status update."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        BASE_COORDINATOR + "NotificationCoordinator.check_connection",
        return_value=False,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_USER_INPUT
        )
        assert result2.get("type") == FlowResultType.FORM
        assert result2.get("errors") == {"base": "missing_status"}


async def test_form_exception(
    hass: HomeAssistant,
    validate_input_all_ok: dict[str, AsyncMock | MagicMock],
) -> None:
    """Test other exceptions."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.nasweb.config_flow.validate_input",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"], TEST_USER_INPUT
        )
        assert result2.get("type") == FlowResultType.FORM
        assert result2.get("errors") == {"base": "unknown"}


async def test_form_already_configured(
    hass: HomeAssistant,
    validate_input_all_ok: dict[str, AsyncMock | MagicMock],
) -> None:
    """Test already configured device."""
    result = await _add_test_config_entry(hass)
    config_entry = result.get("result")
    assert config_entry is not None
    assert config_entry.unique_id == TEST_SERIAL_NUMBER

    result2_1 = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    result2_2 = await hass.config_entries.flow.async_configure(
        result2_1["flow_id"], TEST_USER_INPUT
    )
    await hass.async_block_till_done()

    assert result2_2.get("type") == FlowResultType.ABORT
    assert result2_2.get("reason") == "already_configured"
