"""Tests for the SVS Subwoofer select platform."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant

from . import SVS_ADDRESS, async_init_integration, entity_id


async def test_lpf_slope_options(
    hass: HomeAssistant, mock_bleak_client: MagicMock
) -> None:
    """LPF slope select exposes the four supported options."""
    with patch("homeassistant.components.svs_subwoofer.PLATFORMS", [Platform.SELECT]):
        await async_init_integration(hass)

    state = hass.states.get(entity_id(hass, "select", SVS_ADDRESS, "lpf_slope"))
    assert state is not None
    assert state.attributes["options"] == ["6 dB", "12 dB", "18 dB", "24 dB"]


async def test_select_lpf_slope(
    hass: HomeAssistant, mock_bleak_client: MagicMock
) -> None:
    """Selecting an LPF slope writes the encoded value."""
    with patch("homeassistant.components.svs_subwoofer.PLATFORMS", [Platform.SELECT]):
        await async_init_integration(hass)

    eid = entity_id(hass, "select", SVS_ADDRESS, "lpf_slope")
    pre = mock_bleak_client.write_gatt_char.await_count
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: eid, ATTR_OPTION: "24 dB"},
        blocking=True,
    )
    assert mock_bleak_client.write_gatt_char.await_count == pre + 1
    assert hass.states.get(eid).state == "24 dB"


async def test_select_preset_loads_preset(
    hass: HomeAssistant, mock_bleak_client: MagicMock
) -> None:
    """Selecting a preset triggers a preset-load and a refresh request."""
    with patch("homeassistant.components.svs_subwoofer.PLATFORMS", [Platform.SELECT]):
        await async_init_integration(hass)

    eid = entity_id(hass, "select", SVS_ADDRESS, "preset")
    pre = mock_bleak_client.write_gatt_char.await_count
    await hass.services.async_call(
        SELECT_DOMAIN,
        SERVICE_SELECT_OPTION,
        {ATTR_ENTITY_ID: eid, ATTR_OPTION: "Preset 2"},
        blocking=True,
    )
    # Preset load (1 frame) + full settings refresh (4 frames)
    assert mock_bleak_client.write_gatt_char.await_count >= pre + 5
