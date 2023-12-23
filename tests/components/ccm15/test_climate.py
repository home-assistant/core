"""Unit test for CCM15 climate platform."""
from unittest.mock import patch

from ccm15 import CCM15DeviceState, CCM15SlaveDevice
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.ccm15.const import DOMAIN
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
)
from homeassistant.const import ATTR_ENTITY_ID, CONF_HOST, CONF_PORT, SERVICE_TURN_OFF
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


async def test_climate_state(
    hass: HomeAssistant, snapshot: SnapshotAssertion, entity_registry: er.EntityRegistry
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

    # Create a dictionary of CCM15SlaveDevice objects
    ccm15_devices = {
        0: CCM15SlaveDevice(bytes.fromhex("000000b0b8001b")),
        1: CCM15SlaveDevice(bytes.fromhex("00000041c0001a")),
    }
    # Create an instance of the CCM15DeviceState class
    device_state = CCM15DeviceState(devices=ccm15_devices)
    with patch(
        "homeassistant.components.ccm15.coordinator.CCM15Device.get_status_async",
        return_value=device_state,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert entity_registry.async_get("climate.0") == snapshot
    assert entity_registry.async_get("climate.1") == snapshot

    assert hass.states.get("climate.0") == snapshot
    assert hass.states.get("climate.1") == snapshot

    with patch(
        "homeassistant.components.ccm15.coordinator.CCM15Device.get_status_async",
        return_value=device_state,
    ), patch(
        "homeassistant.components.ccm15.coordinator.CCM15Device.async_set_state"
    ) as mock_set_state:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_FAN_MODE,
            {ATTR_ENTITY_ID: ["climate.0"], ATTR_FAN_MODE: FAN_HIGH},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_state.assert_called_once()

    with patch(
        "homeassistant.components.ccm15.coordinator.CCM15Device.get_status_async",
        return_value=device_state,
    ), patch(
        "homeassistant.components.ccm15.coordinator.CCM15Device.async_set_state"
    ) as mock_set_state:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: ["climate.0"], ATTR_HVAC_MODE: HVACMode.COOL},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_state.assert_called_once()

    with patch(
        "homeassistant.components.ccm15.coordinator.CCM15Device.get_status_async",
        return_value=device_state,
    ), patch(
        "homeassistant.components.ccm15.coordinator.CCM15Device.async_set_state"
    ) as mock_set_state:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: ["climate.0"], ATTR_TEMPERATURE: 25},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_state.assert_called_once()

    with patch(
        "homeassistant.components.ccm15.coordinator.CCM15Device.get_status_async",
        return_value=device_state,
    ), patch(
        "homeassistant.components.ccm15.coordinator.CCM15Device.async_set_state"
    ) as mock_set_state:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ["climate.0"]},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_state.assert_called_once()

    with patch(
        "homeassistant.components.ccm15.coordinator.CCM15Device.get_status_async",
        return_value=device_state,
    ), patch(
        "homeassistant.components.ccm15.coordinator.CCM15Device.async_set_state"
    ) as mock_set_state:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_TURN_OFF,
            {ATTR_ENTITY_ID: ["climate.0"]},
            blocking=True,
        )
        await hass.async_block_till_done()
        mock_set_state.assert_called_once()
