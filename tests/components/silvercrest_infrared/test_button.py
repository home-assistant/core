"""Test the SilverCrest Infrared button platform."""

from infrared_protocols.codes.silvercrest.fan import SilverCrestFanCode
import pytest
from pytest_homeassistant.common import MockConfigEntry, snapshot_platform
from pytest_homeassistant.components.infrared import EMITTER_ENTITY_ID
from pytest_homeassistant.components.infrared.common import MockInfraredEmitterEntity
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.components.silvercrest_infrared.button import SilverCrestIrbutton
from homeassistant.components.silvercrest_infrared.const import (
    CONF_DEVICE_TYPE,
    CONF_INFRARED_ENTITY_ID,
    DOMAIN,
    SilverCrestIrDeviceType,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


@pytest.mark.parametrize(
    "config_entry",
    [
        SilverCrestIrDeviceType.STVD45A1,
        SilverCrestIrDeviceType.SSVS85A1,
    ],
    indirect=True,
)
@pytest.mark.usefixtures("mock_infrared_emitter_entity")
async def test_setup(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
) -> None:
    """Snapshot test states of button platform."""

    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    await snapshot_platform(hass, entity_registry, snapshot, config_entry.entry_id)


_BUTTON_PRESSES: dict[
    SilverCrestIrDeviceType, list[tuple[SilverCrestIrbutton, int]]
] = {
    SilverCrestIrDeviceType.STVD45A1: [
        (SilverCrestIrbutton.POWER, SilverCrestFanCode.POWER),
        (SilverCrestIrbutton.SPEED, SilverCrestFanCode.SPEED),
        (SilverCrestIrbutton.TIMER, SilverCrestFanCode.TIMER),
        (SilverCrestIrbutton.OSC, SilverCrestFanCode.OSC),
        (SilverCrestIrbutton.MODE, SilverCrestFanCode.MODE),
    ],
    SilverCrestIrDeviceType.SSVS85A1: [
        (SilverCrestIrbutton.POWER, SilverCrestFanCode.POWER),
        (SilverCrestIrbutton.SPEED, SilverCrestFanCode.SPEED),
        (SilverCrestIrbutton.TIMER, SilverCrestFanCode.TIMER),
        (SilverCrestIrbutton.OSC, SilverCrestFanCode.OSC),
        (SilverCrestIrbutton.MIST, SilverCrestFanCode.MODE),
    ],
}


@pytest.mark.parametrize("device_type", list(_BUTTON_PRESSES))
@pytest.mark.usefixtures("infrared_codes")
async def test_button_press(
    hass: HomeAssistant,
    mock_infrared_emitter_entity: MockInfraredEmitterEntity,
    entity_registry: er.EntityRegistry,
    device_type: SilverCrestIrDeviceType,
) -> None:
    """Test button press action."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="Misting fan via Test IR emitter",
        entry_id="1234567890",
        data={
            CONF_DEVICE_TYPE: device_type,
            CONF_INFRARED_ENTITY_ID: EMITTER_ENTITY_ID,
        },
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    for key, expected_codes in _BUTTON_PRESSES[device_type]:
        entity_id = entity_registry.async_get_entity_id(
            BUTTON_DOMAIN, DOMAIN, f"{config_entry.entry_id}_{key}"
        )
        assert entity_id is not None

        mock_infrared_emitter_entity.send_command_calls.clear()

        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )

        assert mock_infrared_emitter_entity.send_command_calls[0] == expected_codes
