"""The tests for YoLink device triggers."""

from pytest_unordered import unordered
from yolink.const import ATTR_DEVICE_DIMMER, ATTR_DEVICE_SMART_REMOTER

from homeassistant.components import automation
from homeassistant.components.device_automation import DeviceAutomationType
from homeassistant.components.yolink import DOMAIN, YOLINK_EVENT
from homeassistant.components.yolink.const import DEV_MODEL_FLEX_FOB_YS3604_UC
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry, async_get_device_automations


async def test_get_triggers(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test we get the expected triggers from a yolink flexfob."""
    config_entry = MockConfigEntry(domain="yolink", data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        model=ATTR_DEVICE_SMART_REMOTER,
        model_id=DEV_MODEL_FLEX_FOB_YS3604_UC,
    )

    expected_triggers = [
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": "button_1_short_press",
            "device_id": device_entry.id,
            "metadata": {},
        },
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": "button_1_long_press",
            "device_id": device_entry.id,
            "metadata": {},
        },
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": "button_2_short_press",
            "device_id": device_entry.id,
            "metadata": {},
        },
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": "button_2_long_press",
            "device_id": device_entry.id,
            "metadata": {},
        },
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": "button_3_short_press",
            "device_id": device_entry.id,
            "metadata": {},
        },
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": "button_3_long_press",
            "device_id": device_entry.id,
            "metadata": {},
        },
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": "button_4_short_press",
            "device_id": device_entry.id,
            "metadata": {},
        },
        {
            "platform": "device",
            "domain": DOMAIN,
            "type": "button_4_long_press",
            "device_id": device_entry.id,
            "metadata": {},
        },
    ]
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entry.id
    )
    assert triggers == unordered(expected_triggers)


async def test_get_triggers_exception(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> None:
    """Test get triggers when device type not flexfob."""
    config_entry = MockConfigEntry(domain="yolink", data={})
    config_entry.add_to_hass(hass)
    device_entity = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={(dr.CONNECTION_NETWORK_MAC, "12:34:56:AB:CD:EF")},
        model=ATTR_DEVICE_DIMMER,
        model_id=None,
    )

    expected_triggers = []
    triggers = await async_get_device_automations(
        hass, DeviceAutomationType.TRIGGER, device_entity.id
    )
    assert triggers == unordered(expected_triggers)


async def test_if_fires_on_event(
    hass: HomeAssistant,
    service_calls: list[ServiceCall],
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test for event triggers firing."""
    mac_address = "12:34:56:AB:CD:EF"
    connection = (dr.CONNECTION_NETWORK_MAC, mac_address)
    config_entry = MockConfigEntry(domain=DOMAIN, data={})
    config_entry.add_to_hass(hass)
    device_entry = device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        connections={connection},
        identifiers={(DOMAIN, mac_address)},
        model=ATTR_DEVICE_SMART_REMOTER,
        model_id=DEV_MODEL_FLEX_FOB_YS3604_UC,
    )

    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": "device",
                        "domain": DOMAIN,
                        "device_id": device_entry.id,
                        "type": "button_1_long_press",
                    },
                    "action": {
                        "service": "yolink.automation",
                        "data": {"message": "service called"},
                    },
                },
            ]
        },
    )

    device = device_registry.async_get_device(connections={connection})
    assert device is not None
    # Fake remote button long press.
    hass.bus.async_fire(
        event_type=YOLINK_EVENT,
        event_data={
            "type": "button_1_long_press",
            "device_id": device.id,
        },
    )
    await hass.async_block_till_done()
    assert len(service_calls) == 1
    assert service_calls[0].data["message"] == "service called"
