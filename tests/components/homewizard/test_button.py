"""Test the identify button for HomeWizard."""
from unittest.mock import MagicMock

from homewizard_energy.errors import DisabledError, RequestError
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components import button
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

pytestmark = [
    pytest.mark.usefixtures("init_integration"),
    pytest.mark.freeze_time("2021-01-01 12:00:00"),
]


@pytest.mark.parametrize(
    "device_fixture", ["HWE-WTR", "SDM230", "SDM630", "HWE-KWH1", "HWE-KWH3"]
)
async def test_identify_button_entity_not_loaded_when_not_available(
    hass: HomeAssistant,
) -> None:
    """Does not load button when device has no support for it."""
    assert not hass.states.get("button.device_identify")


async def test_identify_button(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    mock_homewizardenergy: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Loads button when device has support."""
    assert (state := hass.states.get("button.device_identify"))
    assert snapshot == state

    assert (entity_entry := entity_registry.async_get(state.entity_id))
    assert snapshot == entity_entry

    assert entity_entry.device_id
    assert (device_entry := device_registry.async_get(entity_entry.device_id))
    assert snapshot == device_entry

    assert len(mock_homewizardenergy.identify.mock_calls) == 0
    await hass.services.async_call(
        button.DOMAIN,
        button.SERVICE_PRESS,
        {ATTR_ENTITY_ID: state.entity_id},
        blocking=True,
    )
    assert len(mock_homewizardenergy.identify.mock_calls) == 1

    assert (state := hass.states.get(state.entity_id))
    assert state.state == "2021-01-01T12:00:00+00:00"

    # Raise RequestError when identify is called
    mock_homewizardenergy.identify.side_effect = RequestError()

    with pytest.raises(
        HomeAssistantError,
        match=r"^An error occurred while communicating with HomeWizard device$",
    ):
        await hass.services.async_call(
            button.DOMAIN,
            button.SERVICE_PRESS,
            {ATTR_ENTITY_ID: state.entity_id},
            blocking=True,
        )
    assert len(mock_homewizardenergy.identify.mock_calls) == 2

    assert (state := hass.states.get(state.entity_id))
    assert state.state == "2021-01-01T12:00:00+00:00"

    # Raise RequestError when identify is called
    mock_homewizardenergy.identify.side_effect = DisabledError()

    with pytest.raises(
        HomeAssistantError,
        match=r"^The local API of the HomeWizard device is disabled$",
    ):
        await hass.services.async_call(
            button.DOMAIN,
            button.SERVICE_PRESS,
            {ATTR_ENTITY_ID: state.entity_id},
            blocking=True,
        )

    assert len(mock_homewizardenergy.identify.mock_calls) == 3
    assert (state := hass.states.get(state.entity_id))
    assert state.state == "2021-01-01T12:00:00+00:00"
