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


async def test_q10_set_volume(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    fake_q10_vacuum: FakeDevice,
) -> None:
    """Test setting the Q10 speaker volume."""
    entity_id = "number.roborock_q10_s5_volume"
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "50.0"

    await hass.services.async_call(
        "number",
        SERVICE_SET_VALUE,
        service_data={ATTR_VALUE: 40.0},
        blocking=True,
        target={"entity_id": entity_id},
    )
    assert fake_q10_vacuum.b01_q10_properties is not None
    fake_q10_vacuum.b01_q10_properties.volume.set_volume.assert_awaited_once_with(40)


async def test_q10_set_volume_failure(
    hass: HomeAssistant,
    setup_entry: MockConfigEntry,
    fake_q10_vacuum: FakeDevice,
) -> None:
    """Test a backend error setting the Q10 volume raises HomeAssistantError."""
    entity_id = "number.roborock_q10_s5_volume"
    assert fake_q10_vacuum.b01_q10_properties is not None
    fake_q10_vacuum.b01_q10_properties.volume.set_volume.side_effect = RoborockTimeout
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "number",
            SERVICE_SET_VALUE,
            service_data={ATTR_VALUE: 40.0},
            blocking=True,
            target={"entity_id": entity_id},
        )
