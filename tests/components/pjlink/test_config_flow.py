"""Test the PJLink config flow."""

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from homeassistant import config_entries
from homeassistant.components.pjlink.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .const import DEFAULT_DATA, DEFAULT_DATA_W_ENCODING, DEFAULT_DATA_WO_PORT

from tests.common import MockConfigEntry


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


async def test_user_flow_aborts_if_already_configured(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_projector: MagicMock,
    mock_config_entry: MockConfigEntry,
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


@pytest.mark.parametrize(
    "import_data",
    [DEFAULT_DATA, DEFAULT_DATA_WO_PORT, DEFAULT_DATA_W_ENCODING],
)
async def test_import_creates_entry(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_projector: MagicMock,
    import_data: dict[str, Any],
) -> None:
    """Test importing a YAML config creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=import_data
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "test name"
    assert result["data"] == DEFAULT_DATA
    assert len(mock_setup_entry.mock_calls) == 1


async def test_import_aborts_if_already_configured(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_projector: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test importing a YAML config aborts if already configured."""

    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=DEFAULT_DATA
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
async def test_import_invalid_inputs(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_projector: MagicMock,
    side_effect: type[Exception],
    error_str: str,
) -> None:
    """Test we handle invalid inputs."""

    mock_instance = mock_projector.from_address.return_value
    mock_instance.authenticate.side_effect = side_effect
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data=DEFAULT_DATA
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == error_str
    assert len(mock_setup_entry.mock_calls) == 0
    assert len(hass.config_entries.async_entries(DOMAIN)) == 0
