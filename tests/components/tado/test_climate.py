"""The climate tests for the tado platform."""

from collections.abc import AsyncGenerator
from datetime import timedelta
from unittest.mock import AsyncMock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
from homeassistant.components.tado.const import TYPE_AIR_CONDITIONING
from homeassistant.const import ATTR_ENTITY_ID, ATTR_TEMPERATURE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


@pytest.fixture(autouse=True)
def setup_platforms() -> AsyncGenerator[None]:
    """Set up the platforms for the tests."""
    with patch("homeassistant.components.tado.PLATFORMS", [Platform.CLIMATE]):
        yield


async def trigger_update(hass: HomeAssistant, freezer: FrozenDateTimeFactory) -> None:
    """Trigger an update of the Tado integration.

    Since the binary sensor platform doesn't infer a state immediately without extra requests,
    so adding this here to remove in a follow-up PR.
    """
    freezer.tick(timedelta(minutes=5))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_tado_api: AsyncMock,
) -> None:
    """Test creation of climate entities."""

    await setup_integration(hass, mock_config_entry)
    await trigger_update(hass, freezer)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


async def test_heater_set_temperature(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_tado_api: AsyncMock,
) -> None:
    """Test the set temperature of the heater."""

    await setup_integration(hass, mock_config_entry)
    await trigger_update(hass, freezer)

    with (
        patch(
            "homeassistant.components.tado.coordinator.TadoDataUpdateCoordinator.set_zone_overlay"
        ) as mock_set_state,
        patch(
            "homeassistant.components.tado.coordinator.Tado.get_zone_state",
            return_value={"setting": {"temperature": {"celsius": 22.0}}},
        ),
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_TEMPERATURE,
            {ATTR_ENTITY_ID: "climate.baseboard_heater", ATTR_TEMPERATURE: 22.0},
            blocking=True,
        )

    mock_set_state.assert_called_once()
    snapshot.assert_match(mock_set_state.call_args)


@pytest.mark.parametrize(
    ("hvac_mode", "set_hvac_mode"),
    [
        (HVACMode.HEAT, "HEAT"),
        (HVACMode.DRY, "DRY"),
        (HVACMode.FAN_ONLY, "FAN"),
        (HVACMode.COOL, "COOL"),
        (HVACMode.OFF, "OFF"),
    ],
)
async def test_aircon_set_hvac_mode(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    hvac_mode: HVACMode,
    set_hvac_mode: str,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
    mock_tado_api: AsyncMock,
) -> None:
    """Test the set hvac mode of the air conditioning."""

    mock_tado_api.get_capabilities.return_value.type = TYPE_AIR_CONDITIONING

    await setup_integration(hass, mock_config_entry)
    await trigger_update(hass, freezer)

    mock_tado_api.get_zone_state.return_value.current_hvac_mode = set_hvac_mode
    mock_tado_api.get_zone_state.return_value.current_swing_mode = [
        "MID_UP",
        "MID_DOWN",
        "ON",
        "OFF",
        "UP",
        "MID",
        "DOWN",
    ]

    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: "climate.air_conditioning", ATTR_HVAC_MODE: hvac_mode},
        blocking=True,
    )

    mock_tado_api.get_zone_state.assert_called_once()
    snapshot.assert_match(mock_tado_api.set_zone_overlay.call_args)
