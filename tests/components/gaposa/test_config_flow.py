"""HERE Test the Gaposa config flow."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.gaposa.config_flow import CannotConnect, InvalidAuth
from homeassistant.components.gaposa.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_form(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test we get the form."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "pygaposa.Gaposa.login",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "api_key": "test-apikey",
                "username": "test-username",
                "password": "test-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.CREATE_ENTRY
    assert result2["title"] == "Gaposa Gateway"
    assert result2["data"] == {
        "api_key": "test-apikey",
        "username": "test-username",
        "password": "test-password",
    }
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_invalid_auth(hass: HomeAssistant) -> None:
    """Test we handle invalid auth."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "pygaposa.Gaposa.login",
        side_effect=InvalidAuth,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "api_key": "test-apikey",
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}


async def test_form_cannot_connect(hass: HomeAssistant) -> None:
    """Test we handle cannot connect error."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "pygaposa.Gaposa.login",
        side_effect=CannotConnect,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "api_key": "test-apikey",
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "cannot_connect"}


async def test_form_unknown_error(hass: HomeAssistant) -> None:
    """Test we handle unknown errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "pygaposa.Gaposa.login",
        side_effect=Exception,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "api_key": "test-apikey",
                "username": "test-username",
                "password": "test-password",
            },
        )

    assert result2["type"] == FlowResultType.FORM
    assert result2["errors"] == {"base": "unknown"}


async def test_reauth_flow(hass: HomeAssistant) -> None:
    """Test the reauthentication flow."""
    mock_config = MockConfigEntry(
        domain=DOMAIN,
        data={
            "api_key": "test-apikey",
            "username": "test-username",
            "password": "test-password",
        },
    )
    mock_config.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": mock_config.entry_id,
        },
    )

    assert result["type"] == FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "pygaposa.Gaposa.login",
        return_value=True,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "password": "new-password",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] == FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
