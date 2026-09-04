"""Tests for OpenGarage opener lights."""

from unittest.mock import MagicMock

import pytest

from homeassistant.components import light
from homeassistant.const import ATTR_ENTITY_ID, STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry

ENTITY_ID = "light.garage_abcdef_light"


async def test_light_entity_and_controls(
    hass: HomeAssistant,
    mock_opengarage: MagicMock,
    init_integration: MockConfigEntry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test light creation, state, and idempotent library controls."""
    entry = entity_registry.async_get(ENTITY_ID)
    assert entry
    assert entry.unique_id == "12345_light"
    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_OFF

    mock_opengarage.set_light.return_value = 1
    await hass.services.async_call(
        light.DOMAIN,
        light.SERVICE_TURN_ON,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    mock_opengarage.set_light.assert_awaited_once_with(True)
    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_ON

    await hass.services.async_call(
        light.DOMAIN,
        light.SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: ENTITY_ID},
        blocking=True,
    )

    mock_opengarage.set_light.assert_awaited_with(False)
    assert (state := hass.states.get(ENTITY_ID))
    assert state.state == STATE_OFF


async def test_light_not_created_without_capability(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_opengarage: MagicMock,
) -> None:
    """Test legacy OpenGarage devices do not get a light entity."""
    mock_opengarage.update_state.return_value.pop("light")
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert hass.states.get(ENTITY_ID) is None


@pytest.mark.parametrize(
    ("result", "message"),
    [
        (2, "device key is incorrect"),
        (None, "device is unavailable or does not support light control"),
        (3, "OpenGarage returned error code 3"),
    ],
)
async def test_light_control_error_surfaces_to_user(
    hass: HomeAssistant,
    mock_opengarage: MagicMock,
    init_integration: MockConfigEntry,
    result: int | None,
    message: str,
) -> None:
    """Test light control failures are raised to the service caller."""
    mock_opengarage.set_light.return_value = result

    with pytest.raises(HomeAssistantError, match=message):
        await hass.services.async_call(
            light.DOMAIN,
            light.SERVICE_TURN_ON,
            {ATTR_ENTITY_ID: ENTITY_ID},
            blocking=True,
        )
