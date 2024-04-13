"""Tests for the Elgato switch platform."""

from unittest.mock import MagicMock

from elgato import ElgatoError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.switch import (
    DOMAIN as SWITCH_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

pytestmark = [
    pytest.mark.parametrize("device_fixtures", ["key-light-mini"]),
    pytest.mark.usefixtures("device_fixtures", "init_integration"),
]


@pytest.mark.parametrize(
    ("entity_id", "method"),
    [
        ("switch.frenck_studio_mode", "battery_bypass"),
        ("switch.frenck_energy_saving", "energy_saving"),
    ],
)
async def test_switches(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_elgato: MagicMock,
    snapshot: SnapshotAssertion,
    entity_id: str,
    method: str,
) -> None:
    """Test the Elgato switches."""
    assert (state := hass.states.get(entity_id))
    assert state == snapshot

    assert (entry := entity_registry.async_get(entity_id))
    assert entry == snapshot

    assert entry.device_id
    assert (device_entry := device_registry.async_get(entry.device_id))
    assert device_entry == snapshot

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mocked_method = getattr(mock_elgato, method)
    assert len(mocked_method.mock_calls) == 1
    mocked_method.assert_called_once_with(on=True)

    await hass.services.async_call(
        SWITCH_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    assert len(mocked_method.mock_calls) == 2
    mocked_method.assert_called_with(on=False)

    mocked_method.side_effect = ElgatoError

    with pytest.raises(
        HomeAssistantError, match="An error occurred while updating the Elgato Light"
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    assert len(mocked_method.mock_calls) == 3

    with pytest.raises(
        HomeAssistantError, match="An error occurred while updating the Elgato Light"
    ):
        await hass.services.async_call(
            SWITCH_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    assert len(mocked_method.mock_calls) == 4
