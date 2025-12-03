"""Test Roborock Number platform."""

import pytest
from roborock.exceptions import RoborockTimeout

from homeassistant.components.number import ATTR_VALUE, SERVICE_SET_VALUE
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError

from .conftest import FakeDevice

from tests.common import MockConfigEntry


@pytest.fixture
def platforms() -> list[Platform]:
    """Fixture to set platforms used in the test."""
    return [Platform.NUMBER]


async def test_update_sound_volume(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    fake_vacuum: FakeDevice,
) -> None:
    """Test allowed changing values for number entities."""

    # Ensure that the entity exist, as these test can pass even if there is no entity.
    state = hass.states.get("number.roborock_s7_maxv_volume")
    assert state is not None
    assert state.state == "50.0"

    await hass.services.async_call(
        "number",
        SERVICE_SET_VALUE,
        service_data={ATTR_VALUE: 3.0},
        blocking=True,
        target={"entity_id": "number.roborock_s7_maxv_volume"},
    )

    assert fake_vacuum.v1_properties is not None
    assert fake_vacuum.v1_properties.sound_volume.set_volume.call_count == 1
    assert fake_vacuum.v1_properties.sound_volume.set_volume.call_args[0] == (3.0,)

    # Verify the entity state is updated with the latest information from the trait
    state = hass.states.get("number.roborock_s7_maxv_volume")
    assert state is not None
    assert state.state == "3.0"


async def test_volume_update_failed(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    fake_vacuum: FakeDevice,
) -> None:
    """Test allowed changing values for number entities."""
    assert fake_vacuum.v1_properties is not None
    fake_vacuum.v1_properties.sound_volume.set_volume.side_effect = RoborockTimeout

    # Ensure that the entity exist, as these test can pass even if there is no entity.
    assert hass.states.get("number.roborock_s7_maxv_volume") is not None

    with pytest.raises(HomeAssistantError, match="Failed to update Roborock options"):
        await hass.services.async_call(
            "number",
            SERVICE_SET_VALUE,
            service_data={ATTR_VALUE: 3.0},
            blocking=True,
            target={"entity_id": "number.roborock_s7_maxv_volume"},
        )

    assert fake_vacuum.v1_properties.sound_volume.set_volume.call_count == 1
    assert fake_vacuum.v1_properties.sound_volume.set_volume.call_args[0] == (3.0,)
