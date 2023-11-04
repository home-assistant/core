"""Test the number entity for HomeWizard."""
from unittest.mock import MagicMock

from homewizard_energy.errors import DisabledError, RequestError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import number
from homeassistant.components.homewizard.const import UPDATE_INTERVAL
from homeassistant.components.number import ATTR_VALUE, SERVICE_SET_VALUE
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er
import homeassistant.util.dt as dt_util

from tests.common import async_fire_time_changed


@pytest.mark.usefixtures("init_integration")
@pytest.mark.parametrize("device_fixture", ["HWE-SKT"])
async def test_number_entities(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_homewizardenergy: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test number handles state changes correctly."""
    assert (state := hass.states.get("number.device_status_light_brightness"))
    assert snapshot == state

    assert (entity_entry := entity_registry.async_get(state.entity_id))
    assert snapshot == entity_entry

    assert entity_entry.device_id
    assert (device_entry := device_registry.async_get(entity_entry.device_id))
    assert snapshot == device_entry

    # Test unknown handling
    assert state.state == "100"

    mock_homewizardenergy.state.return_value.brightness = None

    async_fire_time_changed(hass, dt_util.utcnow() + UPDATE_INTERVAL)
    await hass.async_block_till_done()

    assert (state := hass.states.get(state.entity_id))
    assert state.state == STATE_UNKNOWN

    # Test service methods
    assert len(mock_homewizardenergy.state_set.mock_calls) == 0
    await hass.services.async_call(
        number.DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: state.entity_id,
            ATTR_VALUE: 50,
        },
        blocking=True,
    )

    assert len(mock_homewizardenergy.state_set.mock_calls) == 1
    mock_homewizardenergy.state_set.assert_called_with(brightness=127)

    mock_homewizardenergy.state_set.side_effect = RequestError
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            number.DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: state.entity_id,
                ATTR_VALUE: 50,
            },
            blocking=True,
        )

    mock_homewizardenergy.state_set.side_effect = DisabledError
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            number.DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: state.entity_id,
                ATTR_VALUE: 50,
            },
            blocking=True,
        )
