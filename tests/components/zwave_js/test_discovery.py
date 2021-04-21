"""Test discovery of entities for device-specific schemas for the Z-Wave JS integration."""
from typing import List

from homeassistant.components.zwave_js.const import DOMAIN
from homeassistant.components.zwave_js.discovery import ZwaveDiscoveryInfo
from homeassistant.helpers.dispatcher import async_dispatcher_connect

from tests.common import MockConfigEntry


async def test_iblinds_v2(hass, client, iblinds_v2, integration):
    """Test that an iBlinds v2.0 multilevel switch value is discovered as a cover."""
    node = iblinds_v2
    assert node.device_class.specific.label == "Unused"

    state = hass.states.get("light.window_blind_controller")
    assert not state

    state = hass.states.get("cover.window_blind_controller")
    assert state


async def test_ge_12730(hass, client, ge_12730, integration):
    """Test GE 12730 Fan Controller v2.0 multilevel switch is discovered as a fan."""
    node = ge_12730
    assert node.device_class.specific.label == "Multilevel Power Switch"

    state = hass.states.get("light.in_wall_smart_fan_control")
    assert not state

    state = hass.states.get("fan.in_wall_smart_fan_control")
    assert state


async def test_inovelli_lzw36(hass, client, inovelli_lzw36, integration):
    """Test LZW36 Fan Controller multilevel switch endpoint 2 is discovered as a fan."""
    node = inovelli_lzw36
    assert node.device_class.specific.label == "Unused"

    state = hass.states.get("light.family_room_combo")
    assert state.state == "off"

    state = hass.states.get("fan.family_room_combo_2")
    assert state


async def test_vision_security_zl7432(hass, client, vision_security_zl7432):
    """Test Vision Security ZL7432 is caught by the device specific discovery."""
    entry = MockConfigEntry(domain="zwave_js", data={"url": "ws://test.org"})
    entry.add_to_hass(hass)

    disc_infos: List[ZwaveDiscoveryInfo] = []

    def _capture_discovery_info(info: ZwaveDiscoveryInfo) -> None:
        """Capture switch discovery info."""
        disc_infos.append(info)

    async_dispatcher_connect(
        hass, f"{DOMAIN}_{entry.entry_id}_add_switch", _capture_discovery_info
    )

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()
    assert len(disc_infos) == 1
    assert disc_infos[0].platform_hint == "force_update"
