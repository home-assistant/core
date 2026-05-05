"""Test the Zeversolar switch platform."""

from unittest.mock import AsyncMock, MagicMock, patch

from homeassistant.components.zeversolar.const import MINIMUM_LIMIT
from homeassistant.const import (
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import MOCK_SERIAL_NUMBER, MOCK_ZEVERSOLAR_DATA, init_integration

_SWITCH_UNIQUE_ID = f"{MOCK_SERIAL_NUMBER}_output_enabled"


def _get_switch_entity_id(entity_registry: er.EntityRegistry) -> str:
    entity_id = entity_registry.async_get_entity_id(
        "switch", "zeversolar", _SWITCH_UNIQUE_ID
    )
    assert entity_id is not None, (
        f"Switch entity not found in registry (unique_id={_SWITCH_UNIQUE_ID!r})"
    )
    return entity_id


async def test_switch_available_when_probe_passes(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Switch is available when the power limit API probe passes."""
    await init_integration(hass, power_limit_supported=True)

    entity_id = _get_switch_entity_id(entity_registry)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state != STATE_UNAVAILABLE


async def test_switch_unavailable_when_probe_fails(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Switch is unavailable when the power limit API probe fails."""
    await init_integration(hass, power_limit_supported=False)

    entity_id = _get_switch_entity_id(entity_registry)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_UNAVAILABLE


async def test_switch_is_on_at_full_power(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Switch reports ON when power limit is at 100%."""
    await init_integration(hass)

    entity_id = _get_switch_entity_id(entity_registry)
    state = hass.states.get(entity_id)
    assert state is not None
    assert state.state == STATE_ON


async def test_switch_turn_off_ramps_to_minimum(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Turning the switch off ramps the output to MINIMUM_LIMIT."""
    with (
        patch(
            "zeversolar.ZeverSolarClient.get_data",
            return_value=MOCK_ZEVERSOLAR_DATA,
        ),
        patch(
            "homeassistant.components.zeversolar.coordinator.ZeversolarCoordinator._fetch_power_limit",
            return_value=MINIMUM_LIMIT,
        ),
        patch(
            "homeassistant.components.zeversolar.switch.async_ramp",
            new_callable=AsyncMock,
        ) as mock_ramp,
    ):
        await init_integration(hass)
        entity_id = _get_switch_entity_id(entity_registry)
        await hass.services.async_call(
            "switch",
            SERVICE_TURN_OFF,
            {"entity_id": entity_id},
            blocking=True,
        )

    mock_ramp.assert_called_once()
    assert mock_ramp.call_args.args[2] == MINIMUM_LIMIT


async def test_switch_turn_on_ramps_to_full(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """Turning the switch on ramps the output to 100%."""
    with (
        patch(
            "zeversolar.ZeverSolarClient.get_data",
            return_value=MOCK_ZEVERSOLAR_DATA,
        ),
        patch(
            "homeassistant.components.zeversolar.coordinator.ZeversolarCoordinator._fetch_power_limit",
            return_value=100,
        ),
        patch(
            "homeassistant.components.zeversolar.switch.async_ramp",
            new_callable=AsyncMock,
        ) as mock_ramp,
    ):
        await init_integration(hass)
        entity_id = _get_switch_entity_id(entity_registry)
        await hass.services.async_call(
            "switch",
            SERVICE_TURN_ON,
            {"entity_id": entity_id},
            blocking=True,
        )

    mock_ramp.assert_called_once()
    assert mock_ramp.call_args.args[2] == 100


async def test_switch_on_step_updates_coordinator_data(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
) -> None:
    """The on_step callback fired by async_ramp updates coordinator data in real time."""
    adv_response = "\n".join(["0"] * 15)
    adv_response_lines = ["0"] * 15
    adv_response_lines[11] = "100.0"
    adv_response = "\n".join(adv_response_lines)

    mock_resp = AsyncMock()
    mock_resp.text.return_value = adv_response
    mock_get_cm = AsyncMock()
    mock_get_cm.__aenter__.return_value = mock_resp

    mock_session = MagicMock()
    mock_session.get.return_value = mock_get_cm

    with (
        patch(
            "zeversolar.ZeverSolarClient.get_data",
            return_value=MOCK_ZEVERSOLAR_DATA,
        ),
        patch(
            "homeassistant.components.zeversolar.coordinator.ZeversolarCoordinator._fetch_power_limit",
            return_value=100,
        ),
        patch(
            "homeassistant.components.zeversolar.ramp.async_get_clientsession",
            return_value=mock_session,
        ),
        patch(
            "homeassistant.components.zeversolar.ramp._async_write_limit",
            new_callable=AsyncMock,
        ),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        await init_integration(hass)
        entity_id = _get_switch_entity_id(entity_registry)
        await hass.services.async_call(
            "switch",
            SERVICE_TURN_OFF,
            {"entity_id": entity_id},
            blocking=True,
        )
