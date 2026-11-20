"""Test the PJLink config flow."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant import config_entries
from homeassistant.components.pjlink.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import DEFAULT_DATA


async def test_user_flow_creates_entry(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_projector: MagicMock,
) -> None:
    """Test that the user flow creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], DEFAULT_DATA
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test name"
    assert result["data"] == DEFAULT_DATA
    assert len(mock_setup_entry.mock_calls) == 1


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_flow_aborts_if_already_configured(
    hass: HomeAssistant, mock_projector: MagicMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test user flow aborts if already configured."""

    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], DEFAULT_DATA
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.parametrize(
    ("side_effect", "error_str"),
    [
        (RuntimeError, "invalid_auth"),
        (TimeoutError, "cannot_connect"),
        (Exception, "unknown"),
    ],
)
async def test_form_invalid_inputs(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_projector: MagicMock,
    side_effect: type[Exception],
    error_str: str,
) -> None:
    """Test we handle invalid inputs."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    mock_instance = mock_projector.from_address.return_value
    mock_instance.authenticate.side_effect = side_effect
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], DEFAULT_DATA
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error_str}

    mock_instance.authenticate.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], DEFAULT_DATA
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test name"
    assert result["data"] == DEFAULT_DATA
    assert len(mock_setup_entry.mock_calls) == 1
