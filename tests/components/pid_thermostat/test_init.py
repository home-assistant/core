"""Test the PID thermostat integration."""
import pytest

from homeassistant.components.pid_thermostat.const import (
    CONF_HEATER,
    CONF_SENSOR,
    DOMAIN,
)
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.parametrize("platform", ("climate",))
async def test_setup_and_remove_config_entry(
    hass: HomeAssistant,
    platform: str,
) -> None:
    """Test setting up and removing a config entry."""
    sensor = "sensor.input"
    heater = "number.output"

    registry = er.async_get(hass)
    pid_thermostat_entity_id = f"{platform}.my_pid_thermostat"

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_HEATER: heater,
            CONF_SENSOR: sensor,
            CONF_NAME: "My pid_thermostat",
        },
        title="My pid_thermostat",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the entity is registered in the entity registry
    assert registry.async_get(pid_thermostat_entity_id) is not None

    # Check the platform is setup correctly
    state = hass.states.get(pid_thermostat_entity_id)
    assert state.state == "off"

    # Remove the config entry
    assert await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the state and entity registry entry are removed
    assert hass.states.get(pid_thermostat_entity_id) is None
    assert registry.async_get(pid_thermostat_entity_id) is None
