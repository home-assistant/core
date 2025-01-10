"""Helper method tests."""

from unittest.mock import patch

import pytest

from homeassistant.components.tado import TadoDataUpdateCoordinator
from homeassistant.components.tado.const import (
    CONST_OVERLAY_MANUAL,
    CONST_OVERLAY_TADO_DEFAULT,
    CONST_OVERLAY_TADO_MODE,
    CONST_OVERLAY_TIMER,
)
from homeassistant.components.tado.helper import decide_duration, decide_overlay_mode
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant


@pytest.fixture
def entry(request: pytest.FixtureRequest):
    """Fixture for ConfigEntry with optional fallback."""
    fallback = (
        request.param if hasattr(request, "param") else CONST_OVERLAY_TADO_DEFAULT
    )
    return ConfigEntry(
        version=1,
        minor_version=0,
        domain="tado",
        title="Tado",
        data={
            "username": "test-username",
            "password": "test-password",
        },
        options={
            "fallback": fallback,
        },
        source="user",
        unique_id="unique_id",
        entry_id="entry_id",
        discovery_keys="discovery_keys",
    )


def dummy_tado_connector(
    hass: HomeAssistant, entry: ConfigEntry
) -> TadoDataUpdateCoordinator:
    """Return dummy tado connector."""
    return TadoDataUpdateCoordinator(hass, entry)


@pytest.mark.parametrize("entry", [CONST_OVERLAY_TADO_MODE], indirect=True)
async def test_overlay_mode_duration_set(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Test overlay method selection when duration is set."""
    tado = dummy_tado_connector(hass=hass, entry=entry)
    overlay_mode = decide_overlay_mode(coordinator=tado, duration=3600, zone_id=1)
    # Must select TIMER overlay
    assert overlay_mode == CONST_OVERLAY_TIMER


@pytest.mark.parametrize("entry", [CONST_OVERLAY_TADO_MODE], indirect=True)
async def test_overlay_mode_next_time_block_fallback(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Test overlay method selection when duration is not set."""
    tado = dummy_tado_connector(hass=hass, entry=entry)
    overlay_mode = decide_overlay_mode(coordinator=tado, duration=None, zone_id=1)
    # Must fallback to integration wide setting
    assert overlay_mode == CONST_OVERLAY_TADO_MODE


@pytest.mark.parametrize("entry", [CONST_OVERLAY_TADO_DEFAULT], indirect=True)
async def test_overlay_mode_tado_default_fallback(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Test overlay method selection when tado default is selected."""
    zone_fallback = CONST_OVERLAY_MANUAL
    tado = dummy_tado_connector(hass=hass, entry=entry)

    class MockZoneData:
        def __init__(self) -> None:
            self.default_overlay_termination_type = zone_fallback

    zone_id = 1

    zone_data = {"zone": {zone_id: MockZoneData()}}
    with patch.dict(tado.data, zone_data):
        overlay_mode = decide_overlay_mode(
            coordinator=tado, duration=None, zone_id=zone_id
        )
        # Must fallback to zone setting
        assert overlay_mode == zone_fallback


@pytest.mark.parametrize("entry", [CONST_OVERLAY_MANUAL], indirect=True)
async def test_duration_enabled_without_tado_default(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Test duration decide method when overlay is timer and duration is set."""
    overlay = CONST_OVERLAY_TIMER
    expected_duration = 600
    tado = dummy_tado_connector(hass=hass, entry=entry)
    duration = decide_duration(
        coordinator=tado, duration=expected_duration, overlay_mode=overlay, zone_id=0
    )
    # Should return the same duration value
    assert duration == expected_duration


@pytest.mark.parametrize("entry", [CONST_OVERLAY_TIMER], indirect=True)
async def test_duration_enabled_with_tado_default(
    hass: HomeAssistant, entry: ConfigEntry
) -> None:
    """Test overlay method selection when ended up with timer overlay and None duration."""
    zone_fallback = CONST_OVERLAY_TIMER
    expected_duration = 45000
    tado = dummy_tado_connector(hass=hass, entry=entry)

    class MockZoneData:
        def __init__(self) -> None:
            self.default_overlay_termination_duration = expected_duration

    zone_id = 1

    zone_data = {"zone": {zone_id: MockZoneData()}}
    with patch.dict(tado.data, zone_data):
        duration = decide_duration(
            coordinator=tado, duration=None, zone_id=zone_id, overlay_mode=zone_fallback
        )
        # Must fallback to zone timer setting
        assert duration == expected_duration
