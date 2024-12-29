"""Tests for services."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.ohme.const import DOMAIN
from homeassistant.components.ohme.services import ATTR_CONFIG_ENTRY
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_DEVICE_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import entity_registry as er
from . import setup_integration
from tests.common import MockConfigEntry


async def test_list_charge_slots(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_client: MagicMock
) -> None:
    """Test list charge slots service."""

    await setup_integration(hass, mock_config_entry)

    mock_client.slots = [{
        "start": "2024-12-30T04:00:00+00:00",
        "end": "2024-12-30T04:30:39+00:00",
        "energy": 2.042
    }]

    response = await hass.services.async_call(
        DOMAIN,
        "list_charge_slots",
        {
            ATTR_CONFIG_ENTRY: mock_config_entry.entry_id,
        },
        blocking=True,
        return_response=True,
    )

    assert response == {"slots": mock_client.slots}

    # Test error
    with pytest.raises(ServiceValidationError):
        await hass.services.async_call(
            DOMAIN,
            "list_charge_slots",
            {ATTR_CONFIG_ENTRY: "invalid"},
            blocking=True,
        )
