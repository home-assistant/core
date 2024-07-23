"""Test different accessory types: Triggers (Programmable Switches)."""

from unittest.mock import MagicMock

from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.homekit.const import CHAR_PROGRAMMABLE_SWITCH_EVENT
from homeassistant.components.homekit.type_triggers import DeviceTriggerAccessory
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, async_get_device_automations


async def test_programmable_switch_button_fires_on_trigger(
    hass: HomeAssistant,
    hk_driver,
    events,
    demo_cleanup,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test that DeviceTriggerAccessory fires the programmable switch event on trigger."""
    hk_driver.publish = MagicMock()

    demo_config_entry = MockConfigEntry(domain="domain")
    demo_config_entry.add_to_hass(hass)
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "demo", {"demo": {}})
    await hass.async_block_till_done()
    hass.states.async_set("light.ceiling_lights", STATE_OFF)
    await hass.async_block_till_done()

    entry = entity_registry.async_get("light.ceiling_lights")
    assert entry is not None
    device_id = entry.device_id

    device_triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_id
    )
    acc = DeviceTriggerAccessory(
        hass,
        hk_driver,
        "DeviceTriggerAccessory",
        None,
        1,
        None,
        device_id=device_id,
        device_triggers=device_triggers,
    )
    acc.run()
    await acc.async_attach()
    await hass.async_block_till_done()

    assert acc.entity_id is None
    assert acc.device_id is device_id
    assert acc.available is True

    hk_driver.publish.reset_mock()
    hass.states.async_set("light.ceiling_lights", STATE_ON)
    await hass.async_block_till_done()
    assert len(hk_driver.publish.mock_calls) == 2  # one for on, one for toggle
    for call in hk_driver.publish.mock_calls:
        char = acc.get_characteristic(call.args[0]["aid"], call.args[0]["iid"])
        assert char.display_name == CHAR_PROGRAMMABLE_SWITCH_EVENT

    hk_driver.publish.reset_mock()
    hass.states.async_set("light.ceiling_lights", STATE_OFF)
    await hass.async_block_till_done()
    assert len(hk_driver.publish.mock_calls) == 2  # one for on, one for toggle
    for call in hk_driver.publish.mock_calls:
        char = acc.get_characteristic(call.args[0]["aid"], call.args[0]["iid"])
        assert char.display_name == CHAR_PROGRAMMABLE_SWITCH_EVENT
    await acc.stop()
    await hass.async_block_till_done()
