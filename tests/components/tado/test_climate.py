"""The climate tests for the tado platform."""

from collections.abc import AsyncGenerator
from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
import pytest
from syrupy.assertion import SnapshotAssertion
from tadoasync.models import ZoneState

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    HVACMode,
)
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


@pytest.mark.usefixtures("mock_tado_api")
async def test_entities(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test creation of climate entities."""

    await setup_integration(hass, mock_config_entry)
    await trigger_update(hass, freezer)

    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)


@pytest.mark.usefixtures("mock_tado_api")
async def test_heater_set_temperature(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    freezer: FrozenDateTimeFactory,
    mock_config_entry: MockConfigEntry,
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
) -> None:
    """Test the set hvac mode of the air conditioning."""

    await setup_integration(hass, mock_config_entry)
    await trigger_update(hass, freezer)

    # TODO: @ERWIN: continue here

    with (
        patch(
            "homeassistant.components.tado.coordinator.TadoDataUpdateCoordinator.set_zone_overlay"
        ) as mock_set_state,
        patch(
            "homeassistant.components.tado.coordinator.Tado.get_zone_state",
            return_value=ZoneState(
                zone_id=1,
                current_temp=18.7,
                connection=None,
                current_temp_timestamp="2025-01-02T12:51:52.802Z",
                current_humidity=45.1,
                current_humidity_timestamp="2025-01-02T12:51:52.802Z",
                is_away=False,
                current_hvac_action="IDLE",
                current_fan_speed=None,
                current_fan_level=None,
                current_hvac_mode=set_hvac_mode,
                current_swing_mode="OFF",
                current_vertical_swing_mode="OFF",
                current_horizontal_swing_mode="OFF",
                target_temp=16.0,
                available=True,
                power="ON",
                link="ONLINE",
                ac_power_timestamp=None,
                heating_power_timestamp="2025-01-02T13:01:11.758Z",
                ac_power=None,
                heating_power=None,
                heating_power_percentage=0.0,
                tado_mode="HOME",
                overlay_termination_type="MANUAL",
                overlay_termination_timestamp=None,
                default_overlay_termination_type="MANUAL",
                default_overlay_termination_duration=None,
                preparation=False,
                open_window=False,
                open_window_detected=False,
                open_window_attr={},
                precision=0.1,
            ),
        ),
    ):
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_SET_HVAC_MODE,
            {ATTR_ENTITY_ID: "climate.air_conditioning", ATTR_HVAC_MODE: hvac_mode},
            blocking=True,
        )

    mock_set_state.assert_called_once()
    snapshot.assert_match(mock_set_state.call_args)
