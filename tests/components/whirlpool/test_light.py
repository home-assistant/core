"""Test the Whirlpool light platform."""

import pytest
from syrupy.assertion import SnapshotAssertion
import whirlpool

from homeassistant.components.light import (
    DOMAIN as LIGHT_DOMAIN,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from . import init_integration, snapshot_whirlpool_entities


@pytest.fixture(
    params=[
        (
            "light.single_cavity_oven_light",
            "mock_oven_single_cavity_api",
            whirlpool.oven.Cavity.Upper,
        ),
        (
            "light.dual_cavity_oven_upper_oven_light",
            "mock_oven_dual_cavity_api",
            whirlpool.oven.Cavity.Upper,
        ),
        (
            "light.dual_cavity_oven_lower_oven_light",
            "mock_oven_dual_cavity_api",
            whirlpool.oven.Cavity.Lower,
        ),
    ]
)
def oven_light_entity(
    request: pytest.FixtureRequest,
) -> tuple[str, str, whirlpool.oven.Cavity]:
    """Parametrize the oven light entities."""
    return request.param


@pytest.mark.usefixtures("entity_registry_enabled_by_default")
async def test_all_entities(
    hass: HomeAssistant, snapshot: SnapshotAssertion, entity_registry: er.EntityRegistry
) -> None:
    """Test all entities."""
    await init_integration(hass)
    snapshot_whirlpool_entities(hass, entity_registry, snapshot, Platform.LIGHT)


@pytest.mark.parametrize(
    ("service", "expected_state"),
    [(SERVICE_TURN_ON, True), (SERVICE_TURN_OFF, False)],
)
async def test_turn_on_off(
    hass: HomeAssistant,
    oven_light_entity: tuple[str, str, whirlpool.oven.Cavity],
    request: pytest.FixtureRequest,
    service: str,
    expected_state: bool,
) -> None:
    """Test turning the oven light on and off."""
    entity_id, mock_fixture, cavity = oven_light_entity
    mock = request.getfixturevalue(mock_fixture)
    await init_integration(hass)

    await hass.services.async_call(
        LIGHT_DOMAIN,
        service,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    mock.set_light.assert_called_once_with(expected_state, cavity)


@pytest.mark.parametrize("service", [SERVICE_TURN_ON, SERVICE_TURN_OFF])
async def test_turn_on_off_failure(
    hass: HomeAssistant,
    oven_light_entity: tuple[str, str, whirlpool.oven.Cavity],
    request: pytest.FixtureRequest,
    service: str,
) -> None:
    """Test a failed light request raises HomeAssistantError."""
    entity_id, mock_fixture, _ = oven_light_entity
    mock = request.getfixturevalue(mock_fixture)
    mock.set_light.return_value = False
    await init_integration(hass)

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            LIGHT_DOMAIN,
            service,
            {ATTR_ENTITY_ID: entity_id},
            blocking=True,
        )
