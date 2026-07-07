"""Tests for the Plugwise Number integration."""

from unittest.mock import MagicMock

import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry, snapshot_platform


@pytest.mark.parametrize("platforms", [(NUMBER_DOMAIN,)])
@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_adam_number_entities(
    hass: HomeAssistant,
    mock_smile_adam: MagicMock,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    setup_platform: MockConfigEntry,
) -> None:
    """Test Adam number snapshot."""
    await snapshot_platform(hass, entity_registry, snapshot, setup_platform.entry_id)


async def test_adam_temperature_offset_change(
    hass: HomeAssistant, mock_smile_adam: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test changing of the temperature_offset number."""
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: "number.zone_thermostat_jessie_temperature_offset",
            ATTR_VALUE: 1.0,
        },
        blocking=True,
    )

    assert mock_smile_adam.set_number.call_count == 1
    mock_smile_adam.set_number.assert_called_with(
        "6a3bf693d05e48e0b460c815a4fdd09d", "temperature_offset", 1.0
    )


async def test_adam_temperature_offset_out_of_bounds_change(
    hass: HomeAssistant, mock_smile_adam: MagicMock, init_integration: MockConfigEntry
) -> None:
    """Test changing of the temperature_offset number beyond limits."""
    with pytest.raises(ServiceValidationError, match="valid range"):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: "number.zone_thermostat_jessie_temperature_offset",
                ATTR_VALUE: 3.0,
            },
            blocking=True,
        )
