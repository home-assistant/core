"""Tests for the SVS Subwoofer number platform."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from homeassistant.components.number import (
    ATTR_VALUE,
    DOMAIN as NUMBER_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant

from . import SVS_ADDRESS, async_init_integration, entity_id


async def test_volume_set(hass: HomeAssistant, mock_bleak_client: MagicMock) -> None:
    """Setting the volume slider writes through to the coordinator."""
    with patch("homeassistant.components.svs_subwoofer.PLATFORMS", [Platform.NUMBER]):
        await async_init_integration(hass)

    eid = entity_id(hass, "number", SVS_ADDRESS, "volume")
    state = hass.states.get(eid)
    assert state is not None
    assert float(state.attributes["min"]) == -60
    assert float(state.attributes["max"]) == 0

    pre = mock_bleak_client.write_gatt_char.await_count
    await hass.services.async_call(
        NUMBER_DOMAIN,
        SERVICE_SET_VALUE,
        {ATTR_ENTITY_ID: eid, ATTR_VALUE: -25},
        blocking=True,
    )
    assert mock_bleak_client.write_gatt_char.await_count == pre + 1
    state = hass.states.get(eid)
    assert state.state in ("-25.0", "-25")


async def test_peq_q_factor_step(
    hass: HomeAssistant, mock_bleak_client: MagicMock
) -> None:
    """PEQ Q-factor entity exposes a 0.1 step (NumberMode.BOX)."""
    with patch("homeassistant.components.svs_subwoofer.PLATFORMS", [Platform.NUMBER]):
        await async_init_integration(hass)

    state = hass.states.get(entity_id(hass, "number", SVS_ADDRESS, "peq1_q_factor"))
    assert state is not None
    assert float(state.attributes["step"]) == 0.1
    assert float(state.attributes["min"]) == 0.2
    assert float(state.attributes["max"]) == 10.0
