"""Test the Slow PWM integration."""
import pytest

from homeassistant.components.slow_pwm.const import CONF_OUTPUTS, DOMAIN
from homeassistant.const import CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from tests.common import MockConfigEntry


@pytest.mark.parametrize("platform", ("number",))
async def test_setup_and_remove_config_entry(
    hass: HomeAssistant,
    platform: str,
) -> None:
    """Test setting up and removing a config entry."""
    outputs = ["sensor.output_1", "sensor.output_2"]

    registry = er.async_get(hass)
    slow_pwm_entity_id = f"{platform}.my_slow_pwm"

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            CONF_OUTPUTS: outputs,
            CONF_NAME: "My slow_pwm",
        },
        title="My slow_pwm",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the entity is registered in the entity registry
    assert registry.async_get(slow_pwm_entity_id) is not None

    # Check the platform is setup correctly
    state = hass.states.get(slow_pwm_entity_id)
    assert state.state == "0.0"

    # Remove the config entry
    assert await hass.config_entries.async_remove(config_entry.entry_id)
    await hass.async_block_till_done()

    # Check the state and entity registry entry are removed
    assert hass.states.get(slow_pwm_entity_id) is None
    assert registry.async_get(slow_pwm_entity_id) is None
