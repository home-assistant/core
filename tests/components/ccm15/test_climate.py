"""Unit test for CCM15 coordinator component."""
from unittest.mock import AsyncMock, patch

from ccm15 import CCM15DeviceState, CCM15SlaveDevice
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.ccm15.climate import CCM15Climate
from homeassistant.components.ccm15.const import DOMAIN
from homeassistant.components.ccm15.coordinator import CCM15Coordinator
from homeassistant.components.climate import (
    ATTR_FAN_MODE,
    ATTR_HVAC_MODE,
    ATTR_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
    FAN_HIGH,
    SERVICE_SET_FAN_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    SERVICE_TURN_ON,
    HVACMode,
    UnitOfTemperature,
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST, CONF_PORT, SERVICE_TURN_OFF
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_climate_state(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    ccm15_device: AsyncMock,
) -> None:
    """Test the coordinator."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="1.1.1.1",
        data={
            CONF_HOST: "1.1.1.1",
            CONF_PORT: 80,
        },
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entity_registry.async_get("climate.midea_0") == snapshot
    assert entity_registry.async_get("climate.midea_1") == snapshot

    assert hass.states.get("climate.midea_0") == snapshot
    assert hass.states.get("climate.midea_1") == snapshot

    with patch(
        "homeassistant.components.ccm15.coordinator.CCM15Device.async_set_state"
    ) as mock_set_state:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: ["climate.midea_0"], ATTR_FAN_MODE: FAN_HIGH},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_state.assert_called_once()

    with patch(
        "homeassistant.components.ccm15.coordinator.CCM15Device.async_set_state"
    ) as mock_set_state:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: ["climate.midea_0"], ATTR_HVAC_MODE: HVACMode.COOL},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_state.assert_called_once()

    with patch(
        "homeassistant.components.ccm15.coordinator.CCM15Device.async_set_state"
    ) as mock_set_state:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: ["climate.midea_0"], ATTR_TEMPERATURE: 25},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_state.assert_called_once()

    with patch(
        "homeassistant.components.ccm15.coordinator.CCM15Device.async_set_state"
    ) as mock_set_state:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ["climate.midea_0"]},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_state.assert_called_once()

    with patch(
        "homeassistant.components.ccm15.coordinator.CCM15Device.async_set_state"
    ) as mock_set_state:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: ["climate.midea_0"]},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_state.assert_called_once()


async def test_cmm15_data_isread_correctly(
    hass: HomeAssistant, mock_setup_entry: AsyncMock
) -> None:
    """Test the coordinator."""
    # Create a dictionary of CCM15SlaveDevice objects
    ccm15_devices = {
        0: CCM15SlaveDevice(bytes.fromhex("000000b0b8001b")),
        1: CCM15SlaveDevice(bytes.fromhex("00000041c0001a")),
    }
    # Create an instance of the CCM15DeviceState class
    device_state = CCM15DeviceState(devices=ccm15_devices)
    with patch(
        "ccm15.CCM15Device.CCM15Device.get_status_async",
        return_value=device_state,
    ):
        coordinator = CCM15Coordinator(hass, "1.1.1.1", "80")
        await coordinator.async_refresh()

    data = coordinator.data
    devices = []
    for ac_index in data.devices:
        devices.append(CCM15Climate(coordinator.get_host(), ac_index, coordinator))
    assert len(data.devices) == 2
    assert len(devices) == 2
    first_climate = list(devices)[0]
    assert first_climate is not None
    assert first_climate.available is True
    assert first_climate.temperature_unit == UnitOfTemperature.CELSIUS
    assert first_climate.current_temperature == 27
    assert first_climate.target_temperature == 23
    assert len(devices) == 2
    climate = next(iter(devices))
    assert climate is not None
    assert climate.coordinator == coordinator
    assert climate._ac_index == 0
    assert coordinator.data == data
    assert climate.unique_id == "1.1.1.1.0"

    # Now test empty return from Network
    device_state = CCM15DeviceState(devices={})
    with patch(
        "ccm15.CCM15Device.CCM15Device.get_status_async",
        return_value=device_state,
    ):
        await coordinator.async_refresh()

    assert first_climate is not None
    assert first_climate.available is False
    assert first_climate.hvac_mode is None
    assert first_climate.current_temperature is None
    assert first_climate.target_temperature is None
