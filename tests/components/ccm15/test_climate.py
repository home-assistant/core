"""Unit test for CCM15 coordinator component."""
from unittest.mock import AsyncMock, patch

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

    assert entity_registry.async_get("climate.0") == snapshot
    assert entity_registry.async_get("climate.1") == snapshot

    assert hass.states.get("climate.0") == snapshot
    assert hass.states.get("climate.1") == snapshot

    with patch(
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
