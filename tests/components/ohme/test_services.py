"""Tests for services."""

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.ohme.const import DOMAIN
from homeassistant.components.ohme.services import (
    ATTR_CONFIG_ENTRY,
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
        {
            "start": "2024-12-30T04:00:00+00:00",
            "end": "2024-12-30T04:30:39+00:00",
            "energy": 2.042,
        }
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
