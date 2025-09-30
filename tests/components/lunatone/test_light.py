"""Tests for the Lunatone integration."""

from datetime import timedelta
from unittest.mock import AsyncMock, PropertyMock, patch

from freezegun.api import FrozenDateTimeFactory
from lunatone_rest_api_client import Device, Devices
from lunatone_rest_api_client.models import ControlData
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    Platform,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed

TEST_ENTITY_ID = "light.device_1"


async def test_setup(
    hass: HomeAssistant,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_info: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Lunatone configuration entry loading/unloading."""
    await setup_integration(hass, mock_config_entry)

    entities = hass.states.async_all(Platform.LIGHT)
    for entity_state in entities:
        entity_entry = entity_registry.async_get(entity_state.entity_id)
        assert entity_entry == snapshot(name=f"{entity_entry.entity_id}-entry")
        assert entity_state == snapshot(name=f"{entity_entry.entity_id}-state")


async def test_turn_on_off(
    hass: HomeAssistant,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_info: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the light can be turned on and off."""

    def fake_control(device: Device, control_data: ControlData):
        if control_data.switchable is not None:
            device._data.features.switchable.status = control_data.switchable

    device_list = [
        Device(mock_lunatone_devices._auth, d)
        for d in mock_lunatone_devices._data.devices
    ]
    for dev in device_list:
        dev.async_control = AsyncMock(
            side_effect=lambda data, d=dev: fake_control(d, data)
        )
        dev.async_update = AsyncMock()

    with patch.object(Devices, "devices", new_callable=PropertyMock) as mock_prop:
        mock_prop.return_value = device_list

        await setup_integration(hass, mock_config_entry)

        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: TEST_ENTITY_ID},
            blocking=True,
        )

        assert mock_lunatone_devices.devices[0].is_on

        await hass.services.async_call(
            LIGHT_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: TEST_ENTITY_ID},
            blocking=True,
        )

        assert not mock_lunatone_devices.devices[0].is_on
        assert mock_lunatone_devices.devices[0].async_control.call_count == 2


async def test_coordinator_update_handling(
    hass: HomeAssistant,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_info: AsyncMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the coordinator update handling."""

    async def fake_update():
        device = mock_lunatone_devices._data.devices[0]
        device.features.switchable.status = not device.features.switchable.status

    await setup_integration(hass, mock_config_entry)

    mock_lunatone_devices.async_update.side_effect = fake_update

    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_ON

    freezer.tick(timedelta(seconds=10))
    async_fire_time_changed(hass)

    state = hass.states.get(TEST_ENTITY_ID)
    assert state.state == STATE_OFF
