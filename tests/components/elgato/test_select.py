"""Tests for the Elgato select platform."""

from unittest.mock import MagicMock

from elgato import ElgatoError, PowerOnBehavior
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

pytestmark = [
    pytest.mark.parametrize("device_fixtures", ["key-light"]),
    pytest.mark.usefixtures("device_fixtures", "init_integration"),
]


async def test_power_on_behavior(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_elgato: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Elgato power-on behavior select."""
    entity_id = "select.frenck_power_on_behavior"

    assert (state := hass.states.get(entity_id))
    assert state == snapshot

    assert (entry := entity_registry.async_get(entity_id))
    assert entry == snapshot

    assert entry.device_id
    assert (device_entry := device_registry.async_get(entry.device_id))
    assert device_entry == snapshot

    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "use_defaults"},
        blocking=True,
    )

    assert len(mock_elgato.power_on_behavior.mock_calls) == 1
    mock_elgato.power_on_behavior.assert_called_once_with(
        behavior=PowerOnBehavior.USE_DEFAULTS
    )

    mock_elgato.power_on_behavior.side_effect = ElgatoError

    with pytest.raises(
        HomeAssistantError,
        match="An unknown error occurred while communicating with the Elgato device",
    ):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {ATTR_ENTITY_ID: entity_id, ATTR_OPTION: "restore_last"},
            blocking=True,
        )

    assert len(mock_elgato.power_on_behavior.mock_calls) == 2
