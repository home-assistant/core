"""Test the number entity for HomeWizard."""

from unittest.mock import MagicMock

from homewizard_energy.errors import DisabledError, RequestError
from homewizard_energy.models import CombinedModels, Measurement, State, System
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

pytestmark = [
    pytest.mark.usefixtures("init_integration"),
]


@pytest.mark.parametrize("device_fixture", ["HWE-SKT-11", "HWE-SKT-21"])
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

    mock_homewizardenergy.combined.return_value = CombinedModels(
        device=None, measurement=Measurement(), system=System(), state=State()
    )

    async_fire_time_changed(hass, dt_util.utcnow() + UPDATE_INTERVAL)
    await hass.async_block_till_done()

    assert (state := hass.states.get(state.entity_id))
    assert state.state == STATE_UNKNOWN

    # Test service methods
    assert len(mock_homewizardenergy.state.mock_calls) == 0
    await hass.services.async_call(
        number.DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: state.entity_id,
            ATTR_VALUE: 50,
        },
        blocking=True,
    )

    assert len(mock_homewizardenergy.system.mock_calls) == 1
    mock_homewizardenergy.system.assert_called_with(status_led_brightness_pct=50)

    mock_homewizardenergy.system.side_effect = RequestError
    with pytest.raises(
        HomeAssistantError,
        match=r"^An error occurred while communicating with HomeWizard device$",
    ):
        await hass.services.async_call(
            number.DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: state.entity_id,
                ATTR_VALUE: 50,
            },
            blocking=True,
        )

    mock_homewizardenergy.system.side_effect = DisabledError
    with pytest.raises(
        HomeAssistantError,
        match=r"^The local API is disabled$",
    ):
        await hass.services.async_call(
            number.DOMAIN,
            SERVICE_SET_VALUE,
            {
                ATTR_ENTITY_ID: state.entity_id,
                ATTR_VALUE: 50,
            },
            blocking=True,
        )


@pytest.mark.parametrize(
    "device_fixture", ["HWE-P1", "HWE-WTR", "SDM230", "SDM630", "HWE-KWH1", "HWE-KWH3"]
)
async def test_entities_not_created_for_device(hass: HomeAssistant) -> None:
    """Does not load number when device has no support for it."""
    assert not hass.states.get("number.device_status_light_brightness")
