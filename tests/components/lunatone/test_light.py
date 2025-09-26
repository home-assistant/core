"""Tests for the Lunatone integration."""

from unittest.mock import AsyncMock

from homeassistant.components.light import DOMAIN as LIGHT_DOMAIN
from homeassistant.components.lunatone.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF, SERVICE_TURN_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from . import DEVICE_DATA_LIST, SERIAL_NUMBER, setup_integration

from tests.common import MockConfigEntry

TEST_ENTITY_ID = "light.device_1"


async def test_setup(
    hass: HomeAssistant,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_info: AsyncMock,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the Lunatone configuration entry loading/unloading."""
    await setup_integration(hass, mock_config_entry)

    for device_data in DEVICE_DATA_LIST:
        expected_unique_id = f"{SERIAL_NUMBER}-device{device_data.id}"

        entry = entity_registry.async_get(f"light.device_{device_data.id}")
        assert entry
        assert entry.device_id
        assert entry.unique_id == expected_unique_id

        device_entry = device_registry.async_get(entry.device_id)
        assert device_entry
        assert device_entry.identifiers == {(DOMAIN, expected_unique_id)}
        assert device_entry.name == f"Device {device_data.id}"


async def test_turn_on_off(
    hass: HomeAssistant,
    mock_lunatone_devices: AsyncMock,
    mock_lunatone_info: AsyncMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the light can be turned on and off."""
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
) -> None:
    """Test the coordinator update handling."""
    await setup_integration(hass, mock_config_entry)

    coordinator_devices = mock_config_entry.runtime_data.coordinator_devices

    coordinator_devices.devices_api._data.devices[0].features.switchable.status = True
    entity = hass.data["light"].get_entity(TEST_ENTITY_ID)
    entity._handle_coordinator_update()
    assert entity.is_on

    coordinator_devices.devices_api._data.devices[0].features.switchable.status = False
    entity = hass.data["light"].get_entity(TEST_ENTITY_ID)
    entity._handle_coordinator_update()
    assert not entity.is_on
