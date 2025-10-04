"""Tests for the tado integration."""

import requests_mock

from homeassistant.components.tado import CONF_REFRESH_TOKEN, DOMAIN
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry, async_load_fixture


async def async_init_integration(
    hass: HomeAssistant,
    skip_setup: bool = False,
):
    """Set up the tado integration in Home Assistant."""

    token_fixture = "token.json"
    devices_fixture = "devices.json"
    mobile_devices_fixture = "mobile_devices.json"
    me_fixture = "me.json"
    weather_fixture = "weather.json"
    home_fixture = "home.json"
    home_state_fixture = "home_state.json"
    zones_fixture = "zones.json"
    zone_states_fixture = "zone_states.json"

    # WR1 Device
    device_wr1_fixture = "device_wr1.json"

    # Smart AC with fanLevel, Vertical and Horizontal swings
    zone_6_state_fixture = "smartac4.with_fanlevel.json"
    zone_6_capabilities_fixture = "zone_with_fanlevel_horizontal_vertical_swing.json"

    # Smart AC with Swing
    zone_5_state_fixture = "smartac3.with_swing.json"
    zone_5_capabilities_fixture = "zone_with_swing_capabilities.json"

    # Water Heater 2
    zone_4_state_fixture = "tadov2.water_heater.heating.json"
    zone_4_capabilities_fixture = "water_heater_zone_capabilities.json"

    # Smart AC
    zone_3_state_fixture = "smartac3.cool_mode.json"
    zone_3_capabilities_fixture = "zone_capabilities.json"

    # Water Heater
    zone_2_state_fixture = "tadov2.water_heater.auto_mode.json"
    zone_2_capabilities_fixture = "water_heater_zone_capabilities.json"

    # Tado V2 with manual heating
    zone_1_state_fixture = "tadov2.heating.manual_mode.json"
    zone_1_capabilities_fixture = "tadov2.zone_capabilities.json"

    # Device Temp Offset
    device_temp_offset = "device_temp_offset.json"

    # Zone Default Overlay
    zone_def_overlay = "zone_default_overlay.json"

    with requests_mock.mock() as m:
        m.post(
            "https://auth.tado.com/oauth/token",
            text=await async_load_fixture(hass, token_fixture, DOMAIN),
        )
        m.get(
            "https://my.tado.com/api/v2/me",
            text=await async_load_fixture(hass, me_fixture, DOMAIN),
        )
        m.get(
            "https://my.tado.com/api/v2/homes/1/",
            text=await async_load_fixture(hass, home_fixture, DOMAIN),
        )
        m.get(
            "https://my.tado.com/api/v2/homes/1/weather",
            text=await async_load_fixture(hass, weather_fixture, DOMAIN),
        )
        m.get(
            "https://my.tado.com/api/v2/homes/1/state",
            text=await async_load_fixture(hass, home_state_fixture, DOMAIN),
        )
        m.get(
            "https://my.tado.com/api/v2/homes/1/devices",
            text=await async_load_fixture(hass, devices_fixture, DOMAIN),
        )
        m.get(
            "https://my.tado.com/api/v2/homes/1/mobileDevices",
            text=await async_load_fixture(hass, mobile_devices_fixture, DOMAIN),
        )
        m.get(
            "https://my.tado.com/api/v2/devices/WR1/",
            text=await async_load_fixture(hass, device_wr1_fixture, DOMAIN),
        )
        m.get(
            "https://my.tado.com/api/v2/devices/WR1/temperatureOffset",
            text=await async_load_fixture(hass, device_temp_offset, DOMAIN),
        )
        m.get(
            "https://my.tado.com/api/v2/devices/WR4/temperatureOffset",
            text=await async_load_fixture(hass, device_temp_offset, DOMAIN),
        )
        m.get(
            "https://my.tado.com/api/v2/homes/1/zones",
            text=await async_load_fixture(hass, zones_fixture, DOMAIN),
        )
        m.get(
            "https://my.tado.com/api/v2/homes/1/zoneStates",
            text=await async_load_fixture(hass, zone_states_fixture, DOMAIN),
        )
        m.get(
            "https://my.tado.com/api/v2/homes/1/zones/6/capabilities",
            text=await async_load_fixture(hass, zone_6_capabilities_fixture, DOMAIN),
        )
        m.get(
            "https://my.tado.com/api/v2/homes/1/zones/5/capabilities",
            text=await async_load_fixture(hass, zone_5_capabilities_fixture, DOMAIN),
        )
        m.get(
            "https://my.tado.com/api/v2/homes/1/zones/4/capabilities",
            text=await async_load_fixture(hass, zone_4_capabilities_fixture, DOMAIN),
        )
        m.get(
            "https://my.tado.com/api/v2/homes/1/zones/3/capabilities",
            text=await async_load_fixture(hass, zone_3_capabilities_fixture, DOMAIN),
        )
        m.get(
            "https://my.tado.com/api/v2/homes/1/zones/2/capabilities",
            text=await async_load_fixture(hass, zone_2_capabilities_fixture, DOMAIN),
        )
        m.get(
            "https://my.tado.com/api/v2/homes/1/zones/1/capabilities",
            text=await async_load_fixture(hass, zone_1_capabilities_fixture, DOMAIN),
        )
        m.get(
            "https://my.tado.com/api/v2/homes/1/zones/1/defaultOverlay",
            text=await async_load_fixture(hass, zone_def_overlay, DOMAIN),
        )
        m.get(
            "https://my.tado.com/api/v2/homes/1/zones/2/defaultOverlay",
            text=await async_load_fixture(hass, zone_def_overlay, DOMAIN),
        )
        m.get(
            "https://my.tado.com/api/v2/homes/1/zones/3/defaultOverlay",
            text=await async_load_fixture(hass, zone_def_overlay, DOMAIN),
        )
        m.get(
            "https://my.tado.com/api/v2/homes/1/zones/4/defaultOverlay",
            text=await async_load_fixture(hass, zone_def_overlay, DOMAIN),
        )
        m.get(
            "https://my.tado.com/api/v2/homes/1/zones/5/defaultOverlay",
            text=await async_load_fixture(hass, zone_def_overlay, DOMAIN),
        )
        m.get(
            "https://my.tado.com/api/v2/homes/1/zones/6/defaultOverlay",
            text=await async_load_fixture(hass, zone_def_overlay, DOMAIN),
        )
        m.get(
            "https://my.tado.com/api/v2/homes/1/zones/6/state",
            text=await async_load_fixture(hass, zone_6_state_fixture, DOMAIN),
        )
        m.get(
            "https://my.tado.com/api/v2/homes/1/zones/5/state",
            text=await async_load_fixture(hass, zone_5_state_fixture, DOMAIN),
        )
        m.get(
            "https://my.tado.com/api/v2/homes/1/zones/4/state",
            text=await async_load_fixture(hass, zone_4_state_fixture, DOMAIN),
        )
        m.get(
            "https://my.tado.com/api/v2/homes/1/zones/3/state",
            text=await async_load_fixture(hass, zone_3_state_fixture, DOMAIN),
        )
        m.get(
            "https://my.tado.com/api/v2/homes/1/zones/2/state",
            text=await async_load_fixture(hass, zone_2_state_fixture, DOMAIN),
        )
        m.get(
            "https://my.tado.com/api/v2/homes/1/zones/1/state",
            text=await async_load_fixture(hass, zone_1_state_fixture, DOMAIN),
        )
        m.post(
            "https://login.tado.com/oauth2/token",
            text=await async_load_fixture(hass, token_fixture, DOMAIN),
        )
        entry = MockConfigEntry(
            domain=DOMAIN,
            version=2,
            data={
                CONF_REFRESH_TOKEN: "mock-token",
            },
            options={"fallback": "NEXT_TIME_BLOCK"},
        )
        entry.add_to_hass(hass)

        if not skip_setup:
            await hass.config_entries.async_setup(entry.entry_id)
            await hass.async_block_till_done()

        # For a first refresh
        await entry.runtime_data.coordinator.async_refresh()
        await entry.runtime_data.mobile_coordinator.async_refresh()
        await hass.async_block_till_done()
