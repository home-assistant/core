"""Tests for HomematicIP Cloud lights."""
import logging

import pytest

from tests.components.homematicip_cloud.fakeserver_tests.helper import (
    get_and_check_device_basics,
)

_LOGGER = logging.getLogger(__name__)


@pytest.mark.asyncio
async def test_hmip_light(hass, fake_hmip_hap):
    """Test HomematicipLight."""
    device_id = "light.treppe"
    device_name = "Treppe"
    device_model = "HmIP-BSL"

    device = get_and_check_device_basics(hass, device_id, device_name, device_model)

    assert device.state == "on"
    await hass.services.async_call(
        "light", "turn_off", {"entity_id": device_id}, blocking=True
    )

    await fake_hmip_hap.get_state()
    await hass.async_block_till_done()
    device = hass.states.get(device_id)
    assert device.state == "off"


# HomematicipLightMeasuring
# HomematicipDimmer


@pytest.mark.asyncio
async def test_hmip_notification_light(hass, fake_hmip_hap):
    """Test HomematicipNotificationLight."""
    device_id = "light.treppe_top_notification"
    device_name = "Treppe Top Notification"
    device_model = "HmIP-BSL"

    device = get_and_check_device_basics(hass, device_id, device_name, device_model)

    assert device.state == "off"

    await hass.services.async_call(
        "light", "turn_on", {"entity_id": device_id}, blocking=True
    )
    await fake_hmip_hap.get_state()
    await hass.async_block_till_done()
    device = hass.states.get(device_id)
    assert device.state == "on"
    assert device.attributes["color_name"] == "RED"
    assert device.attributes["brightness"] == 255

    await hass.services.async_call(
        "light", "turn_off", {"entity_id": device_id}, blocking=True
    )
    await fake_hmip_hap.get_state()
    await hass.async_block_till_done()
    device = hass.states.get(device_id)
    assert device.state == "off"

    await hass.services.async_call(
        "light",
        "turn_on",
        {"entity_id": device_id, "brightness": "100", "hs_color": [120, 100]},
        blocking=True,
    )
    await fake_hmip_hap.get_state()
    await hass.async_block_till_done()
    device = hass.states.get(device_id)
    assert device.state == "on"
    assert device.attributes["color_name"] == "GREEN"
    assert device.attributes["brightness"] == 100
