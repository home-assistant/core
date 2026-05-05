"""Test the Zeversolar number platform."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.zeversolar.const import MINIMUM_LIMIT
from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MOCK_SERIAL_NUMBER, MOCK_ZEVERSOLAR_DATA, init_integration

_NUMBER_UNIQUE_ID = f"{MOCK_SERIAL_NUMBER}_power_limit_control"


def _get_number_entity_id(entity_registry: er.EntityRegistry) -> str:
    entity_id = entity_registry.async_get_entity_id(
        "number", "zeversolar", _NUMBER_UNIQUE_ID
    )
    assert entity_id is not None, (
        f"Number entity not found in registry (unique_id={_NUMBER_UNIQUE_ID!r})"
    )
    return entity_id


async def test_number_available_when_probe_passes(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Number entity is available when the power limit API probe passes."""
    await init_integration(hass, power_limit_supported=True)

    entity_id = _get_number_entity_id(entity_registry)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE


async def test_number_unavailable_when_probe_fails(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Number entity is unavailable when the power limit API probe fails."""
    await init_integration(hass, power_limit_supported=False)

    entity_id = _get_number_entity_id(entity_registry)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_number_initial_value_is_100(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Number entity shows 100% after setup (default power limit)."""
    await init_integration(hass)

    entity_id = _get_number_entity_id(entity_registry)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == "100"


@pytest.mark.parametrize("target", [50, MINIMUM_LIMIT, 100])
async def test_number_set_value_ramps_to_target(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    target: int,
) -> None:
    """Setting the number triggers a ramp to the requested value."""
    with (
        patch(
            "zeversolar.ZeverSolarClient.get_data",
            return_value=MOCK_ZEVERSOLAR_DATA,
        ),
        patch(
            "homeassistant.components.zeversolar.coordinator.ZeversolarCoordinator._fetch_power_limit",
            return_value=target,
        ),
        patch(
            "homeassistant.components.zeversolar.number.async_ramp",
            new_callable=AsyncMock,
        ) as mock_ramp,
    ):
        await init_integration(hass)
        entity_id = _get_number_entity_id(entity_registry)
        await hass.services.async_call(
            "number",
            "set_value",
            {"entity_id": entity_id, "value": target},
            blocking=True,
        )

    mock_ramp.assert_called_once()
    assert mock_ramp.call_args.args[2] == target
