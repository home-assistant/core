from homeassistant.components import device_automation
from homeassistant.components.device_automation import DeviceAutomationType

DOMAIN = "connectsense"

async def test_device_actions_triggers_conditions(hass, setup_entry, device_id, domain):
    # Ensure entities/device are registered
    await hass.async_block_till_done()

    trig_map = await device_automation.async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, [device_id]
    )

    trig_list = trig_map.get(device_id, trig_map if isinstance(trig_map, list) else [])

    trig_types = {t["type"] for t in trig_list if t["domain"] == domain}
    assert {"reboot_started_any", "reboot_started_power_fail", "reboot_started_ping_fail"} <= trig_types

async def test_trigger_filtering(hass, setup_entry, device_id, domain):
    evt_type = f"{domain}_reboot_started"
    fired = []

    async def _cb(event, context=None):
        if isinstance(event, dict):
            fired.append(event.get("trigger"))
        else:
            fired.append(getattr(event, "data", event))

    trig_conf = {
        "platform": "device",
        "domain": domain,
        "device_id": device_id,
        "type": "reboot_started_power_fail",
    }

    from homeassistant.components.connectsense import device_trigger as cs_trigger
    await hass.async_block_till_done()

    unsub = await cs_trigger.async_attach_trigger(
        hass,
        trig_conf,
        _cb,
        {"platform": "device", "trigger_data": {}, "variables": {}},
    )
    try:
        await hass.async_block_till_done()

        # Non-matching type
        hass.bus.async_fire(evt_type, {"device_id": device_id, "type": "reboot_started_ping_fail"})
        await hass.async_block_till_done()
        assert not fired

        # Matching type
        hass.bus.async_fire(evt_type, {"device_id": device_id, "type": "reboot_started_power_fail"})
        await hass.async_block_till_done()
        assert fired
    finally:
        unsub()
