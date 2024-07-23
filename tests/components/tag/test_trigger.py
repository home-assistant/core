"""Tests for tag triggers."""

import pytest

from homeassistant.components import automation
from homeassistant.components.tag import async_scan_tag
from homeassistant.components.tag.const import DEVICE_ID, DOMAIN, TAG_ID
from homeassistant.const import ATTR_ENTITY_ID, SERVICE_TURN_OFF
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import async_mock_service


@pytest.fixture(autouse=True, name="stub_blueprint_populate")
def stub_blueprint_populate_autouse(stub_blueprint_populate: None) -> None:
    """Stub copying the blueprints to the config folder."""


@pytest.fixture
def tag_setup(hass, hass_storage):
    """Tag setup."""

    async def _storage(items=None):
        if items is None:
            hass_storage[DOMAIN] = {
                "key": DOMAIN,
                "version": 1,
                "data": {"items": [{"id": "test tag"}]},
            }
        else:
            hass_storage[DOMAIN] = items
        config = {DOMAIN: {}}
        return await async_setup_component(hass, DOMAIN, config)

    return _storage


@pytest.fixture
def calls(hass):
    """Track calls to a mock service."""
    return async_mock_service(hass, "test", "automation")


async def test_triggers(hass: HomeAssistant, tag_setup, calls) -> None:
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

    assert len(calls) == 1
    assert calls[0].data["message"] == "service called"
    assert calls[0].data["id"] == 0

    await hass.services.async_call(
        automation.DOMAIN,
        SERVICE_TURN_OFF,
        {ATTR_ENTITY_ID: "automation.test"},
        blocking=True,
    )

    await async_scan_tag(hass, "abc123", None)
    await hass.async_block_till_done()

    assert len(calls) == 1


async def test_exception_bad_trigger(
    hass: HomeAssistant, calls, caplog: pytest.LogCaptureFixture
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
    hass: HomeAssistant, tag_setup, calls
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

    assert len(calls) == 4
    assert calls[0].data["message"] == "service called"
    assert calls[1].data["message"] == "service called"
    assert calls[2].data["message"] == "service called"
    assert calls[3].data["message"] == "service called"
