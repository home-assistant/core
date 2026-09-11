"""Tests for tag triggers."""

from typing import Any

import attr
import pytest

from homeassistant.components import automation
from homeassistant.components.tag import async_scan_tag
from homeassistant.components.tag.const import DEVICE_ID, DOMAIN, TAG_ID
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.helpers import device_registry as dr
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry


@pytest.fixture
def tag_setup(hass: HomeAssistant, hass_storage: dict[str, Any]):
    """Tag setup."""

    async def _storage(items=None):
        if items is None:
            hass_storage[DOMAIN] = {
                "key": DOMAIN,
                "version": 1,
                "minor_version": 2,
                "data": {"items": [{"id": "test tag", "tag_id": "test tag"}]},
            }
        else:
            hass_storage[DOMAIN] = items
        config = {DOMAIN: {}}
        return await async_setup_component(hass, DOMAIN, config)

    return _storage


async def test_triggers(
    hass: HomeAssistant, tag_setup, service_calls: list[ServiceCall]
) -> None:
    """Test tag triggers."""
    assert await tag_setup()
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "alias": "test",
                    "trigger": {"platform": DOMAIN, TAG_ID: "abc123"},
                    "action": {
                        "service": "test.automation",
                        "data_template": {
                            "message": "service called",
                            "id": "{{ trigger.id}}",
                        },
                    },
                }
            ]
        },
    )

    await hass.async_block_till_done()

    await async_scan_tag(hass, "abc123", None)
    await hass.async_block_till_done()

    assert len(service_calls) == 1
    assert service_calls[0].data["message"] == "service called"
    assert service_calls[0].data["id"] == 0

    await hass.services.async_call(
        automation.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "automation.test"},
        blocking=True,
    )
    assert len(service_calls) == 2

    await async_scan_tag(hass, "abc123", None)
    await hass.async_block_till_done()

    assert len(service_calls) == 2


async def test_exception_bad_trigger(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """Test for exception on event triggers firing."""

    await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {"trigger": {"platform": DOMAIN, "oops": "abc123"}},
                    "action": {
                        "service": "test.automation",
                        "data": {"message": "service called"},
                    },
                }
            ]
        },
    )
    await hass.async_block_till_done()
    assert "Unnamed automation could not be validated" in caplog.text


async def test_multiple_tags_and_devices_trigger(
    hass: HomeAssistant, tag_setup, service_calls: list[ServiceCall]
) -> None:
    """Test multiple tags and devices triggers."""
    assert await tag_setup()
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": DOMAIN,
                        TAG_ID: ["abc123", "def456"],
                        DEVICE_ID: ["ghi789", "jkl0123"],
                    },
                    "action": {
                        "service": "test.automation",
                        "data": {"message": "service called"},
                    },
                }
            ]
        },
    )

    await hass.async_block_till_done()

    # Should not trigger
    await async_scan_tag(hass, tag_id="abc123", device_id=None)
    await async_scan_tag(hass, tag_id="abc123", device_id="invalid")
    await hass.async_block_till_done()

    # Should trigger
    await async_scan_tag(hass, tag_id="abc123", device_id="ghi789")
    await hass.async_block_till_done()
    await async_scan_tag(hass, tag_id="abc123", device_id="jkl0123")
    await hass.async_block_till_done()
    await async_scan_tag(hass, "def456", device_id="ghi789")
    await hass.async_block_till_done()
    await async_scan_tag(hass, "def456", device_id="jkl0123")
    await hass.async_block_till_done()

    assert len(service_calls) == 4
    assert service_calls[0].data["message"] == "service called"
    assert service_calls[1].data["message"] == "service called"
    assert service_calls[2].data["message"] == "service called"
    assert service_calls[3].data["message"] == "service called"


COMPOSITE_ID = "composite00000000000000000000ab"


@pytest.fixture
def split_devices(
    hass: HomeAssistant, device_registry: dr.DeviceRegistry
) -> tuple[dr.DeviceEntry, dr.DeviceEntry]:
    """Create two devices which are splits of a pre-migration composite device."""
    entry_1 = MockConfigEntry(domain="itg1")
    entry_1.add_to_hass(hass)
    entry_2 = MockConfigEntry(domain="itg2")
    entry_2.add_to_hass(hass)
    device_1 = device_registry.async_get_or_create(
        config_entry_id=entry_1.entry_id,
        identifiers={("itg1", "1")},
        name="Split device 1",
    )
    device_2 = device_registry.async_get_or_create(
        config_entry_id=entry_2.entry_id,
        identifiers={("itg2", "1")},
        name="Split device 2",
    )
    device_registry._devices[device_1.id] = attr.evolve(
        device_1, composite_device_id=COMPOSITE_ID
    )
    device_registry._devices[device_2.id] = attr.evolve(
        device_2, composite_device_id=COMPOSITE_ID
    )
    return device_registry._devices[device_1.id], device_registry._devices[device_2.id]


async def test_composite_device_trigger(
    hass: HomeAssistant,
    tag_setup,
    service_calls: list[ServiceCall],
    split_devices: tuple[dr.DeviceEntry, dr.DeviceEntry],
) -> None:
    """Test a tag trigger configured with a pre-migration composite device id.

    The composite device id no longer refers to a registered device; it is expanded to
    the ids of the devices it was split into, so a tag scanned by either split device
    fires the trigger.
    """
    device_1, device_2 = split_devices
    assert await tag_setup()
    assert await async_setup_component(
        hass,
        automation.DOMAIN,
        {
            automation.DOMAIN: [
                {
                    "trigger": {
                        "platform": DOMAIN,
                        TAG_ID: "abc123",
                        DEVICE_ID: COMPOSITE_ID,
                    },
                    "action": {
                        "service": "test.automation",
                        "data": {"message": "service called"},
                    },
                }
            ]
        },
    )

    await hass.async_block_till_done()

    # A scan by the composite id or an unrelated device should not fire
    await async_scan_tag(hass, tag_id="abc123", device_id=COMPOSITE_ID)
    await async_scan_tag(hass, tag_id="abc123", device_id="other_device")
    await hass.async_block_till_done()
    assert len(service_calls) == 0

    # A scan by either split device should fire
    await async_scan_tag(hass, tag_id="abc123", device_id=device_1.id)
    await hass.async_block_till_done()
    await async_scan_tag(hass, tag_id="abc123", device_id=device_2.id)
    await hass.async_block_till_done()

    assert len(service_calls) == 2
    assert service_calls[0].data["message"] == "service called"
    assert service_calls[1].data["message"] == "service called"
