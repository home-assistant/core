"""Test the Arcam Solo config flow."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.arcam_solo.const import DOMAIN
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from tests.common import MockConfigEntry

MOCK_USER_INPUT = {
    CONF_DEVICE: "/dev/ttyUSB0",
}


async def test_user_form_success(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test successful user flow creates an entry."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.arcam_solo.config_flow.ArcamSolo"
    ) as mock_solo:
        mock_solo.return_value.connect = AsyncMock()
        mock_solo.return_value.disconnect = AsyncMock()
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_INPUT,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "Arcam Solo"
    assert result["data"] == MOCK_USER_INPUT
    assert len(mock_setup_entry.mock_calls) == 1
    mock_solo.return_value.connect.assert_awaited_once()
    mock_solo.return_value.disconnect.assert_awaited_once()


@pytest.mark.parametrize(
    ("connect_side_effect", "expected_error"),
    [
        (TimeoutError, "cannot_connect"),
        (OSError, "cannot_connect"),
        (RuntimeError, "unknown"),
    ],
)
async def test_user_form_errors(
    hass: HomeAssistant,
    connect_side_effect: type[Exception],
    expected_error: str,
) -> None:
    """Test user flow connection and unknown errors."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.arcam_solo.config_flow.ArcamSolo"
    ) as mock_solo:
        mock_solo.return_value.connect = AsyncMock(side_effect=connect_side_effect)
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_INPUT,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": expected_error}


async def test_user_form_already_configured(hass: HomeAssistant) -> None:
    """Test user flow aborts for duplicate configuration."""
    entry = MockConfigEntry(domain=DOMAIN, data=MOCK_USER_INPUT)
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    with patch(
        "homeassistant.components.arcam_solo.config_flow.ArcamSolo"
    ) as mock_solo:
        mock_solo.return_value.connect = AsyncMock()
        mock_solo.return_value.disconnect = AsyncMock()
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            MOCK_USER_INPUT,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
