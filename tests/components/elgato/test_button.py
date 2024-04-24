"""Tests for the Elgato Light button platform."""
from unittest.mock import MagicMock

from elgato import ElgatoError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

pytestmark = [
    pytest.mark.parametrize("device_fixtures", ["key-light-mini"]),
    pytest.mark.usefixtures("device_fixtures", "init_integration"),
    pytest.mark.freeze_time("2021-11-13 11:48:00"),
]


@pytest.mark.parametrize(
    ("entity_id", "method"),
    [
        ("button.frenck_identify", "identify"),
        ("button.frenck_restart", "restart"),
    ],
)
async def test_buttons(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_elgato: MagicMock,
    snapshot: SnapshotAssertion,
    entity_id: str,
    method: str,
) -> None:
    """Test the Elgato identify button."""
    assert (state := hass.states.get(entity_id))
    assert state == snapshot

    assert (entry := entity_registry.async_get(entity_id))
    assert entry == snapshot

    assert entry.device_id
    assert (device_entry := device_registry.async_get(entry.device_id))
    assert device_entry == snapshot

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    mocked_method = getattr(mock_elgato, method)
    assert len(mocked_method.mock_calls) == 1
    mocked_method.assert_called_with()

    state = hass.states.get(entity_id)
    assert state
    assert state.state == "2021-11-13T11:48:00+00:00"

    mocked_method.side_effect = ElgatoError

    with pytest.raises(
        HomeAssistantError,
        match="An error occurred while communicating with the Elgato Light",
    ):
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

    assert len(mocked_method.mock_calls) == 2
