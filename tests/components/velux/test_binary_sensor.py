"""Tests for the Velux binary sensor platform."""

from unittest.mock import MagicMock, patch

from homeassistant.components.velux.const import DOMAIN
from homeassistant.const import Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


async def test_rain_sensor_state(
    hass: HomeAssistant,
    mock_window: MagicMock,
    mock_module: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the rain sensor."""
    mock_config_entry.add_to_hass(hass)

    test_entity_id = "binary_sensor.test_window_rain_sensor"

    with (
        patch("homeassistant.components.velux.PLATFORMS", [Platform.BINARY_SENSOR]),
        patch(
            "homeassistant.components.velux.VeluxModule",
            return_value=mock_module,
        ),
    ):
        # setup config entry
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

        # set up the homeassistant component so my entity can get updated
        assert await async_setup_component(hass, "homeassistant", {})
        await hass.async_block_till_done()

        # enable the entity which is disabled by default
        entity_registry = er.async_get(hass)
        entity_entry = entity_registry.async_get_or_create(
            "binary_sensor", DOMAIN, "123456789_rain_sensor"
        )
        assert entity_entry is not None
        assert entity_entry.entity_id == test_entity_id
        assert entity_entry.disabled
        entity_registry.async_update_entity(entity_entry.entity_id, disabled_by=None)

        # Reload the config entry to add the entity to the state machine
        assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # simulate no rain detected
    mock_window.get_limitation.return_value = MagicMock(min_value=0)
    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {"entity_id": test_entity_id},
        blocking=True,
    )
    state = hass.states.get(test_entity_id)
    assert state is not None
    assert state.state == "off"

    # simulate rain detected
    mock_window.get_limitation.return_value = MagicMock(min_value=93)
    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {"entity_id": test_entity_id},
        blocking=True,
    )
    state = hass.states.get(test_entity_id)
    assert state is not None
    assert state.state == "on"
