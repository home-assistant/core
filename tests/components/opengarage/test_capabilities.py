"""Test capability discovery and opener controls."""

import asyncio
from unittest.mock import MagicMock

from opengarage.errors import TransportError, UnsupportedFeatureError
from opengarage.state import normalize_state
import pytest

from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.fixture
async def capable_entry(
    hass: HomeAssistant, mock_opengarage: MagicMock, mock_config_entry: MockConfigEntry
) -> MockConfigEntry:
    """Set up a device with light and lock support."""
    mock_opengarage.get_state.return_value = normalize_state(
        {**mock_opengarage.get_state.return_value.raw, "secv": 2, "light": 0, "lock": 0}
    )
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry


@pytest.mark.usefixtures("capable_entry")
@pytest.mark.parametrize(
    ("domain", "entity_id", "service", "method", "value"),
    [
        pytest.param(
            "light",
            "light.garage_abcdef_light",
            "turn_on",
            "set_light",
            True,
            id="light_on",
        ),
        pytest.param(
            "light",
            "light.garage_abcdef_light",
            "turn_off",
            "set_light",
            False,
            id="light_off",
        ),
        pytest.param(
            "lock",
            "lock.garage_abcdef_remote_control_lock",
            "lock",
            "set_lock",
            True,
            id="lock",
        ),
        pytest.param(
            "lock",
            "lock.garage_abcdef_remote_control_lock",
            "unlock",
            "set_lock",
            False,
            id="unlock",
        ),
    ],
)
@pytest.mark.parametrize(
    "result", [pytest.param(1, id="command"), pytest.param(None, id="no_op")]
)
async def test_control(
    hass: HomeAssistant,
    mock_opengarage: MagicMock,
    domain: str,
    entity_id: str,
    service: str,
    method: str,
    value: bool,
    result: int | None,
) -> None:
    """Use desired-state setters and accept successful no-ops."""
    command = getattr(mock_opengarage, method)
    command.return_value = result
    await hass.services.async_call(
        domain, service, {ATTR_ENTITY_ID: entity_id}, blocking=True
    )
    command.assert_awaited_once_with(value)
    mock_opengarage.toggle_light.assert_not_called()
    mock_opengarage.toggle_lock.assert_not_called()


@pytest.mark.parametrize(
    ("entity_id", "field", "expected"),
    [
        pytest.param("light.garage_abcdef_light", "light", "on", id="light"),
        pytest.param(
            "lock.garage_abcdef_remote_control_lock", "lock", "locked", id="lock"
        ),
    ],
)
async def test_capability_lifecycle(
    hass: HomeAssistant,
    mock_opengarage: MagicMock,
    init_integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
    entity_id: str,
    field: str,
    expected: str,
) -> None:
    """Discover capabilities after setup and retain entity identity if they disappear."""
    assert hass.states.get(entity_id) is None
    coordinator = init_integration.runtime_data
    legacy = mock_opengarage.get_state.return_value.raw
    mock_opengarage.get_state.return_value = normalize_state({**legacy, field: 1})
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == expected
    unique_id = entity_registry.async_get(entity_id).unique_id
    mock_opengarage.get_state.return_value = normalize_state(legacy)
    await coordinator.async_refresh()
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE
    mock_opengarage.get_state.return_value = normalize_state({**legacy, field: 1})
    await coordinator.async_refresh()
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == expected
    assert entity_registry.async_get(entity_id).unique_id == unique_id
    assert (
        len(
            [
                entry
                for entry in entity_registry.entities.values()
                if entry.unique_id == unique_id
            ]
        )
        == 1
    )


@pytest.mark.usefixtures("capable_entry")
@pytest.mark.parametrize(
    ("domain", "entity_id", "service", "method"),
    [
        pytest.param(
            "light", "light.garage_abcdef_light", "turn_on", "set_light", id="light"
        ),
        pytest.param(
            "lock",
            "lock.garage_abcdef_remote_control_lock",
            "lock",
            "set_lock",
            id="lock",
        ),
    ],
)
@pytest.mark.parametrize(
    "error",
    [
        pytest.param(TransportError("offline"), id="transport"),
        pytest.param(UnsupportedFeatureError("unsupported"), id="unsupported"),
    ],
)
async def test_control_failure(
    hass: HomeAssistant,
    mock_opengarage: MagicMock,
    domain: str,
    entity_id: str,
    service: str,
    method: str,
    error: Exception,
) -> None:
    """Expose command errors without claiming the requested state."""
    before = hass.states.get(entity_id).state
    getattr(mock_opengarage, method).side_effect = error
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            domain, service, {ATTR_ENTITY_ID: entity_id}, blocking=True
        )
    assert hass.states.get(entity_id).state == before


@pytest.mark.usefixtures("capable_entry")
async def test_serialized_lock_commands(
    hass: HomeAssistant, mock_opengarage: MagicMock
) -> None:
    """Concurrent requests cannot overlap read-before-toggle operations."""
    active = 0
    maximum_active = 0

    async def set_lock(engaged: bool) -> int:
        nonlocal active, maximum_active
        active += 1
        maximum_active = max(maximum_active, active)
        await asyncio.sleep(0)
        active -= 1
        return 1

    mock_opengarage.set_lock.side_effect = set_lock
    await asyncio.gather(
        hass.services.async_call(
            "lock",
            "lock",
            {ATTR_ENTITY_ID: "lock.garage_abcdef_remote_control_lock"},
            blocking=True,
        ),
        hass.services.async_call(
            "lock",
            "unlock",
            {ATTR_ENTITY_ID: "lock.garage_abcdef_remote_control_lock"},
            blocking=True,
        ),
    )
    assert maximum_active == 1
    assert mock_opengarage.set_lock.await_count == 2
