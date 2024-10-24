"""The tests for climate entities of evohome.

All evohome systems have controllers and at least one zone.
"""

from __future__ import annotations

from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_PRESET_MODE,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_PRESET_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, Platform
from homeassistant.core import HomeAssistant

from .const import TEST_INSTALLS


@pytest.mark.parametrize("install", TEST_INSTALLS)
async def test_zone_set_hvac_mode(
    hass: HomeAssistant,
    zone_id: str,
    snapshot: SnapshotAssertion,
) -> None:
    """Test climate methods of a evohome-compatible zone."""

    results = []

    # SERVICE_SET_HVAC_MODE(HVACMode.HEAT)
    with patch("evohomeasync2.zone.Zone.reset_mode") as mock_fcn:
        await hass.services.async_call(
            Platform.CLIMATE,
            SERVICE_SET_HVAC_MODE,
            {
                ATTR_ENTITY_ID: zone_id,
                ATTR_HVAC_MODE: HVACMode.HEAT,
            },
            blocking=True,
        )

        assert mock_fcn.await_count == 1
        assert mock_fcn.await_args.args == ()
        assert mock_fcn.await_args.kwargs == {}

    # SERVICE_SET_HVAC_MODE(HVACMode.OFF)
    with patch("evohomeasync2.zone.Zone.set_temperature") as mock_fcn:
        await hass.services.async_call(
            Platform.CLIMATE,
            SERVICE_SET_HVAC_MODE,
            {
                ATTR_ENTITY_ID: zone_id,
                ATTR_HVAC_MODE: HVACMode.OFF,
            },
            blocking=True,
        )

        assert mock_fcn.await_count == 1

        results.append(mock_fcn.await_args.args)
        results.append(mock_fcn.await_args.kwargs)

    assert results == snapshot


@pytest.mark.parametrize("install", TEST_INSTALLS)
async def test_zone_set_preset_mode(
    hass: HomeAssistant,
    zone_id: str,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test climate methods of a evohome-compatible zone."""

    freezer.move_to("2024-07-10T12:00:00Z")
    results = []

    # SERVICE_SET_PRESET_MODE(none)
    with patch("evohomeasync2.zone.Zone.reset_mode") as mock_fcn:
        await hass.services.async_call(
            Platform.CLIMATE,
            SERVICE_SET_PRESET_MODE,
            {
                ATTR_ENTITY_ID: zone_id,
                ATTR_PRESET_MODE: "none",
            },
            blocking=True,
        )

        assert mock_fcn.await_count == 1
        assert mock_fcn.await_args.args == ()
        assert mock_fcn.await_args.kwargs == {}

    # SERVICE_SET_PRESET_MODE(permanent)
    with patch("evohomeasync2.zone.Zone.set_temperature") as mock_fcn:
        await hass.services.async_call(
            Platform.CLIMATE,
            SERVICE_SET_PRESET_MODE,
            {
                ATTR_ENTITY_ID: zone_id,
                ATTR_PRESET_MODE: "permanent",
            },
            blocking=True,
        )

        assert mock_fcn.await_count == 1

        results.append(mock_fcn.await_args.args)
        results.append(mock_fcn.await_args.kwargs)

    # SERVICE_SET_PRESET_MODE(temporary)
    with patch("evohomeasync2.zone.Zone.set_temperature") as mock_fcn:
        await hass.services.async_call(
            Platform.CLIMATE,
            SERVICE_SET_PRESET_MODE,
            {
                ATTR_ENTITY_ID: zone_id,
                ATTR_PRESET_MODE: "temporary",
            },
            blocking=True,
        )

        assert mock_fcn.await_count == 1

        results.append(mock_fcn.await_args.args)
        results.append(mock_fcn.await_args.kwargs)

    assert results == snapshot


@pytest.mark.parametrize("install", TEST_INSTALLS)
async def test_zone_set_temperature(
    hass: HomeAssistant,
    zone_id: str,
    freezer: FrozenDateTimeFactory,
    snapshot: SnapshotAssertion,
) -> None:
    """Test climate methods of a evohome-compatible zone."""

    freezer.move_to("2024-07-10T12:00:00Z")
    results = []

    # SERVICE_SET_TEMPERATURE(temp)
    with patch("evohomeasync2.zone.Zone.set_temperature") as mock_fcn:
        await hass.services.async_call(
            Platform.CLIMATE,
            SERVICE_SET_TEMPERATURE,
            {
                ATTR_ENTITY_ID: zone_id,
                ATTR_TEMPERATURE: 19.1,
            },
            blocking=True,
        )

        assert mock_fcn.await_count == 1

        results.append(mock_fcn.await_args.args)
        results.append(mock_fcn.await_args.kwargs)

    assert results == snapshot
