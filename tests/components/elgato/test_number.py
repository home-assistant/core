"""Tests for the Elgato number platform."""

from unittest.mock import MagicMock

from elgato import ElgatoError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

pytestmark = [pytest.mark.usefixtures("init_integration")]


@pytest.mark.parametrize("device_fixtures", ["key-light"])
@pytest.mark.parametrize(
    ("entity_id", "value", "expected"),
    [
        ("number.frenck_power_on_brightness", 50, {"brightness": 50}),
        ("number.frenck_power_on_color_temperature", 5000, {"temperature": 200}),
    ],
)
async def test_numbers(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_elgato: MagicMock,
    snapshot: SnapshotAssertion,
    entity_id: str,
    value: float,
    expected: dict[str, int],
) -> None:
    """Test the Elgato numbers."""
    assert (state := hass.states.get(entity_id))
    assert state == snapshot

    assert (entry := entity_registry.async_get(entity_id))
    assert entry == snapshot

    assert entry.device_id
    assert (device_entry := device_registry.async_get(entry.device_id))
    assert device_entry == snapshot

    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: value},
        blocking=True,
    )

    assert len(mock_elgato.power_on_behavior.mock_calls) == 1
    mock_elgato.power_on_behavior.assert_called_once_with(**expected)

    mock_elgato.power_on_behavior.side_effect = ElgatoError

    with pytest.raises(
        HomeAssistantError,
        match="An unknown error occurred while communicating with the Elgato device",
    ):
        await hass.services.async_call(
            NUMBER_DOMAIN,
            SERVICE_SET_VALUE,
            {ATTR_ENTITY_ID: entity_id, ATTR_VALUE: value},
            blocking=True,
        )

    assert len(mock_elgato.power_on_behavior.mock_calls) == 2


@pytest.mark.parametrize("device_fixtures", ["light-strip"])
async def test_power_on_temperature_unknown(hass: HomeAssistant) -> None:
    """Test a light that powers on to a color instead of a temperature.

    It reports a power-on temperature of zero, which is not a temperature.
    The entity still exists, because whether the device reports the field is
    a property of the device, while what it currently holds is not.
    """
    assert hass.states.get("number.frenck_power_on_brightness")

    assert (state := hass.states.get("number.frenck_power_on_color_temperature"))
    assert state.state == STATE_UNKNOWN


@pytest.mark.parametrize(
    ("device_fixtures", "expected_range"),
    [
        ("key-light", (2900, 6993)),
        ("light-strip", (3500, 6500)),
    ],
)
async def test_power_on_temperature_range(
    hass: HomeAssistant,
    expected_range: tuple[int, int],
) -> None:
    """Test the number stays inside what the device can actually do.

    A light that does color reaches less far at either end, and the number
    has to agree with the light entity about that.
    """
    minimum, maximum = expected_range

    assert (state := hass.states.get("number.frenck_power_on_color_temperature"))
    assert state.attributes["min"] == minimum
    assert state.attributes["max"] == maximum
