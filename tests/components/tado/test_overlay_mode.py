"""Overlay method selection tests."""
from unittest.mock import patch

from homeassistant.components.tado.const import (
    CONST_OVERLAY_MANUAL,
    CONST_OVERLAY_TADO_DEFAULT,
    CONST_OVERLAY_TADO_MODE,
    CONST_OVERLAY_TIMER,
)
from homeassistant.core import HomeAssistant

from .util import dummy_tado_connector


async def test_overlay_mode_duration_set(hass: HomeAssistant) -> None:
    """Test overlay method selection when duration is set."""

    tado = dummy_tado_connector(hass=hass, fallback=CONST_OVERLAY_TADO_MODE)
    overlay_mode = tado.decide_overlay_mode(
        duration="01:00:00",
        zone_id=1,
    )
    # Must select TIMER overlayu
    assert overlay_mode == CONST_OVERLAY_TIMER


async def test_overlay_mode_next_time_block_fallback(hass: HomeAssistant) -> None:
    """Test overlay method selection when duration is not set."""
    integration_fallback = CONST_OVERLAY_TADO_MODE
    tado = dummy_tado_connector(hass=hass, fallback=integration_fallback)
    overlay_mode = tado.decide_overlay_mode(
        duration=None,
        zone_id=1,
    )
    # Must fallback to integration wide setting
    assert overlay_mode == integration_fallback


async def test_overlay_mode_tado_default_fallback(hass: HomeAssistant) -> None:
    """Test overlay method selection when tado default is selected."""
    integration_fallback = CONST_OVERLAY_TADO_DEFAULT
    zone_fallback = CONST_OVERLAY_MANUAL

    class MockZoneData:
        def __init__(self) -> None:
            self.default_overlay_termination_type = zone_fallback

    zone_id = 1
    tado = dummy_tado_connector(hass=hass, fallback=integration_fallback)

    zone_data = {"zone": {zone_id: MockZoneData()}}
    with patch.dict(tado.data, zone_data):
        overlay_mode = tado.decide_overlay_mode(
            duration=None,
            zone_id=zone_id,
        )
        # Must fallback to zone setting
        assert overlay_mode == zone_fallback
