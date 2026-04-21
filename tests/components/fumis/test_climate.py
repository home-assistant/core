"""Tests for the Fumis climate entity."""

from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from fumis import (
    FumisAuthenticationError,
    FumisConnectionError,
    FumisError,
    FumisStoveOfflineError,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.climate import (
    ATTR_HVAC_MODE,
    ATTR_TEMPERATURE,
    DOMAIN as CLIMATE_DOMAIN,
    SERVICE_SET_HVAC_MODE,
    SERVICE_SET_TEMPERATURE,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    HVACMode,
)
from homeassistant.components.fumis.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import async_fire_time_changed

pytestmark = pytest.mark.usefixtures("init_integration")


async def test_climate_entity(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Fumis climate entity."""
    assert (state := hass.states.get("climate.clou_duo"))
    assert state == snapshot

    assert (entity_entry := entity_registry.async_get(state.entity_id))
    assert entity_entry == snapshot

    assert entity_entry.device_id
    assert (device_entry := device_registry.async_get(entity_entry.device_id))
    assert device_entry == snapshot


async def test_set_hvac_mode_heat(
    hass: HomeAssistant,
    mock_fumis: MagicMock,
) -> None:
    """Test setting HVAC mode to heat."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: "climate.clou_duo", ATTR_HVAC_MODE: HVACMode.HEAT},
        blocking=True,
    )

    mock_fumis.turn_on.assert_called_once()


async def test_set_hvac_mode_off(
    hass: HomeAssistant,
    mock_fumis: MagicMock,
) -> None:
    """Test setting HVAC mode to off."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_HVAC_MODE,
        {ATTR_ENTITY_ID: "climate.clou_duo", ATTR_HVAC_MODE: HVACMode.OFF},
        blocking=True,
    )

    mock_fumis.turn_off.assert_called_once()


async def test_set_temperature(
    hass: HomeAssistant,
    mock_fumis: MagicMock,
) -> None:
    """Test setting the target temperature."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_SET_TEMPERATURE,
        {ATTR_ENTITY_ID: "climate.clou_duo", ATTR_TEMPERATURE: 22.5},
        blocking=True,
    )

    mock_fumis.set_target_temperature.assert_called_once_with(22.5)


async def test_turn_on(
    hass: HomeAssistant,
    mock_fumis: MagicMock,
) -> None:
    """Test turning on the stove."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: "climate.clou_duo"},
        blocking=True,
    )

    mock_fumis.turn_on.assert_called_once()


async def test_turn_off(
    hass: HomeAssistant,
    mock_fumis: MagicMock,
) -> None:
    """Test turning off the stove."""
    await hass.services.async_call(
        CLIMATE_DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "climate.clou_duo"},
        blocking=True,
    )

    mock_fumis.turn_off.assert_called_once()


@pytest.mark.parametrize(
    ("side_effect", "expected_translation_key"),
    [
        (FumisAuthenticationError, "authentication_error"),
        (FumisStoveOfflineError, "stove_offline"),
        (FumisConnectionError, "communication_error"),
        (FumisError, "unknown_error"),
    ],
)
async def test_climate_error_handling(
    hass: HomeAssistant,
    mock_fumis: MagicMock,
    side_effect: type[Exception],
    expected_translation_key: str,
) -> None:
    """Test error handling for climate actions."""
    mock_fumis.turn_on.side_effect = side_effect

    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            CLIMATE_DOMAIN,
            SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: "climate.clou_duo"},
            blocking=True,
        )

    assert exc_info.value.translation_domain == DOMAIN
    assert exc_info.value.translation_key == expected_translation_key


@pytest.mark.parametrize(
    "side_effect",
    [
        FumisAuthenticationError,
        FumisStoveOfflineError,
        FumisConnectionError,
        FumisError,
    ],
)
async def test_climate_unavailable_on_update_error(
    hass: HomeAssistant,
    mock_fumis: MagicMock,
    freezer: FrozenDateTimeFactory,
    side_effect: type[Exception],
) -> None:
    """Test climate entity becomes unavailable on update error and recovers."""
    mock_fumis.update_info.side_effect = side_effect

    freezer.tick(timedelta(seconds=35))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get("climate.clou_duo"))
    assert state.state == STATE_UNAVAILABLE

    mock_fumis.update_info.side_effect = None

    freezer.tick(timedelta(seconds=35))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert (state := hass.states.get("climate.clou_duo"))
    assert state.state != STATE_UNAVAILABLE
