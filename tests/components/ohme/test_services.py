"""Tests for services."""

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

from ohme import ChargeSlot
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.ohme.const import DOMAIN
from homeassistant.components.ohme.services import (
    ATTR_CONFIG_ENTRY,
    ATTR_PRICE_CAP,
    SERVICE_LIST_CHARGE_SLOTS,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError

from . import setup_integration

from tests.common import MockConfigEntry


async def test_list_charge_slots(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test list charge slots service."""

    await setup_integration(hass, mock_config_entry)

    mock_client.slots = [
        ChargeSlot(
            datetime.fromisoformat("2024-12-30T04:00:00+00:00"),
            datetime.fromisoformat("2024-12-30T04:30:39+00:00"),
            2.042,
        )
    ]

    assert snapshot == await hass.services.async_call(
        DOMAIN,
        "list_charge_slots",
        {
            ATTR_CONFIG_ENTRY: mock_config_entry.entry_id,
        },
        blocking=True,
        return_response=True,
    )


async def test_set_price_cap(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test set price cap service."""

    await setup_integration(hass, mock_config_entry)
    mock_client.async_change_price_cap = AsyncMock()

    await hass.services.async_call(
        DOMAIN,
        "set_price_cap",
        {
            ATTR_CONFIG_ENTRY: mock_config_entry.entry_id,
            ATTR_PRICE_CAP: 10.0,
        },
        blocking=True,
    )

    mock_client.async_change_price_cap.assert_called_once_with(cap=10.0)


async def test_list_charge_slots_exception(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test list charge slots service."""

    await setup_integration(hass, mock_config_entry)

    # Test error
    with pytest.raises(
        ServiceValidationError, match="Invalid config entry provided. Got invalid"
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_LIST_CHARGE_SLOTS,
            {ATTR_CONFIG_ENTRY: "invalid"},
            blocking=True,
            return_response=True,
        )
