"""Binary sensor tests."""
from zoneminder.monitor import Monitor, MonitorState, TimePeriod
from zoneminder.zm import ZoneMinder

from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.components.zoneminder import const
from homeassistant.components.zoneminder.sensor import CONF_INCLUDE_ARCHIVED
from homeassistant.config import async_process_ha_core_config
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_MONITORED_CONDITIONS,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_PLATFORM,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import DOMAIN as HASS_DOMAIN, HomeAssistant
from homeassistant.setup import async_setup_component

from tests.async_mock import MagicMock, patch
from tests.common import MockConfigEntry


async def test_async_setup_entry(hass: HomeAssistant) -> None:
    """Test setup of sensor entities."""

    def _get_events(monitor_id: int, time_period: TimePeriod, include_archived: bool):
        enum_list = [name for name in dir(TimePeriod) if not name.startswith("_")]
        tp_index = enum_list.index(time_period.name)
        return (100 * monitor_id) + (tp_index * 10) + include_archived

    def _monitor1_get_events(time_period: TimePeriod, include_archived: bool):
        return _get_events(1, time_period, include_archived)

    def _monitor2_get_events(time_period: TimePeriod, include_archived: bool):
        return _get_events(2, time_period, include_archived)

    with patch(
        "homeassistant.components.zoneminder.common.ZoneMinder", autospec=ZoneMinder
    ) as zoneminder_mock:
        monitor1 = MagicMock(spec=Monitor)
        monitor1.name = "monitor1"
        monitor1.mjpeg_image_url = "mjpeg_image_url1"
        monitor1.still_image_url = "still_image_url1"
        monitor1.is_recording = True
        monitor1.is_available = True
        monitor1.function = MonitorState.MONITOR
        monitor1.get_events.side_effect = _monitor1_get_events

        monitor2 = MagicMock(spec=Monitor)
        monitor2.name = "monitor2"
        monitor2.mjpeg_image_url = "mjpeg_image_url2"
        monitor2.still_image_url = "still_image_url2"
        monitor2.is_recording = False
        monitor2.is_available = False
        monitor2.function = MonitorState.MODECT
        monitor2.get_events.side_effect = _monitor2_get_events

        zm_client: ZoneMinder = MagicMock(spec=ZoneMinder)
        zm_client.get_zms_url.return_value = "http://host1/path_zms1"
        zm_client.login.return_value = True
        zm_client.get_monitors.return_value = [monitor1, monitor2]

        zoneminder_mock.return_value = zm_client

        config_entry = MockConfigEntry(
            domain=const.DOMAIN,
            unique_id="host1",
            data={
                CONF_HOST: "host1",
                CONF_USERNAME: "username1",
                CONF_PASSWORD: "password1",
                CONF_PATH: "path1",
                const.CONF_PATH_ZMS: "path_zms1",
                CONF_SSL: False,
                CONF_VERIFY_SSL: True,
            },
        )
        config_entry.add_to_hass(hass)

        hass_config = {
            HASS_DOMAIN: {},
            SENSOR_DOMAIN: [
                {
                    CONF_PLATFORM: const.DOMAIN,
                    CONF_INCLUDE_ARCHIVED: True,
                    CONF_MONITORED_CONDITIONS: ["all", "day"],
                }
            ],
        }

        await async_process_ha_core_config(hass, hass_config[HASS_DOMAIN])
        await async_setup_component(hass, HASS_DOMAIN, hass_config)
        await async_setup_component(hass, SENSOR_DOMAIN, hass_config)
        await hass.async_block_till_done()
        await async_setup_component(hass, const.DOMAIN, hass_config)
        await hass.async_block_till_done()

        await hass.services.async_call(
            HASS_DOMAIN, "update_entity", {ATTR_ENTITY_ID: "sensor.monitor1_status"}
        )
        await hass.services.async_call(
            HASS_DOMAIN, "update_entity", {ATTR_ENTITY_ID: "sensor.monitor1_events"}
        )
        await hass.services.async_call(
            HASS_DOMAIN,
            "update_entity",
            {ATTR_ENTITY_ID: "sensor.monitor1_events_last_day"},
        )
        await hass.services.async_call(
            HASS_DOMAIN, "update_entity", {ATTR_ENTITY_ID: "sensor.monitor2_status"}
        )
        await hass.services.async_call(
            HASS_DOMAIN, "update_entity", {ATTR_ENTITY_ID: "sensor.monitor2_events"}
        )
        await hass.services.async_call(
            HASS_DOMAIN,
            "update_entity",
            {ATTR_ENTITY_ID: "sensor.monitor2_events_last_day"},
        )
        await hass.async_block_till_done()
        assert (
            hass.states.get("sensor.monitor1_status").state
            == MonitorState.MONITOR.value
        )
        assert hass.states.get("sensor.monitor1_events").state == "101"
        assert hass.states.get("sensor.monitor1_events_last_day").state == "111"
        assert hass.states.get("sensor.monitor2_status").state == "unavailable"
        assert hass.states.get("sensor.monitor2_events").state == "201"
        assert hass.states.get("sensor.monitor2_events_last_day").state == "211"

        monitor1.function = MonitorState.NONE
        monitor2.function = MonitorState.NODECT
        await hass.services.async_call(
            HASS_DOMAIN, "update_entity", {ATTR_ENTITY_ID: "sensor.monitor1_status"}
        )
        await hass.services.async_call(
            HASS_DOMAIN, "update_entity", {ATTR_ENTITY_ID: "sensor.monitor1_events"}
        )
        await hass.services.async_call(
            HASS_DOMAIN,
            "update_entity",
            {ATTR_ENTITY_ID: "sensor.monitor1_events_last_day"},
        )
        await hass.services.async_call(
            HASS_DOMAIN, "update_entity", {ATTR_ENTITY_ID: "sensor.monitor2_status"}
        )
        await hass.services.async_call(
            HASS_DOMAIN, "update_entity", {ATTR_ENTITY_ID: "sensor.monitor2_events"}
        )
        await hass.services.async_call(
            HASS_DOMAIN,
            "update_entity",
            {ATTR_ENTITY_ID: "sensor.monitor2_events_last_day"},
        )
        await hass.async_block_till_done()
        assert (
            hass.states.get("sensor.monitor1_status").state == MonitorState.NONE.value
        )
        assert hass.states.get("sensor.monitor1_events").state == "101"
        assert hass.states.get("sensor.monitor1_events_last_day").state == "111"
        assert hass.states.get("sensor.monitor2_status").state == "unavailable"
        assert hass.states.get("sensor.monitor2_events").state == "201"
        assert hass.states.get("sensor.monitor2_events_last_day").state == "211"
