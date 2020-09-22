"""Binary sensor tests."""
from typing import Optional

from zoneminder.monitor import Monitor, MonitorState, TimePeriod
from zoneminder.zm import ZoneMinder

from homeassistant.components.camera import DOMAIN as CAMERA_DOMAIN, STATE_RECORDING
from homeassistant.components.zoneminder import async_setup_entry
from homeassistant.components.zoneminder.const import CONF_PATH_ZMS, DOMAIN
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    STATE_IDLE,
    STATE_UNAVAILABLE,
)
from homeassistant.core import DOMAIN as HASS_DOMAIN, HomeAssistant
from homeassistant.setup import async_setup_component

from tests.async_mock import MagicMock, patch
from tests.common import MockConfigEntry


@patch("homeassistant.components.zoneminder.common.ZoneMinder", autospec=ZoneMinder)
async def test_async_setup_entry(zoneminder_mock, hass: HomeAssistant) -> None:
    """Test setup of camera entities."""
    monitor1_events = {
        TimePeriod.ALL.period: 10,
        TimePeriod.MONTH.period: 9,
        TimePeriod.WEEK.period: 8,
        TimePeriod.DAY.period: 7,
        TimePeriod.HOUR.period: 6,
    }

    def get_events_monitor1(
        time_period: TimePeriod, include_archived: bool
    ) -> Optional[int]:
        return monitor1_events[time_period.period] + int(include_archived)

    monitor1 = MagicMock(spec=Monitor)
    monitor1.id = 1
    monitor1.name = "monitor1"
    monitor1.mjpeg_image_url = "mjpeg_image_url1"
    monitor1.still_image_url = "still_image_url1"
    monitor1.is_recording = False
    monitor1.is_available = False
    monitor1.function = MonitorState.NONE
    monitor1.get_events.side_effect = get_events_monitor1

    camera1_entity_id = "camera.monitor1"

    zm_client: ZoneMinder = MagicMock(spec=ZoneMinder)
    zm_client.get_zms_url.return_value = "http://host1/path_zms1"
    zm_client.login.return_value = True
    zm_client.get_monitors.return_value = [monitor1]

    zoneminder_mock.return_value = zm_client

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="host1",
        data={
            CONF_HOST: "host1",
            CONF_USERNAME: "username1",
            CONF_PASSWORD: "password1",
            CONF_PATH: "path1",
            CONF_PATH_ZMS: "path_zms1",
            CONF_SSL: False,
            CONF_VERIFY_SSL: True,
        },
    )
    config_entry.add_to_hass(hass)

    await async_setup_component(hass, HASS_DOMAIN, {})
    assert await async_setup_entry(hass, config_entry)
    await hass.async_block_till_done()

    # Assert initial states.
    await hass.services.async_call(
        HASS_DOMAIN, "update_entity", {ATTR_ENTITY_ID: camera1_entity_id}
    )
    await hass.async_block_till_done()

    state1 = hass.states.get(camera1_entity_id)
    assert state1.state == STATE_UNAVAILABLE

    # Assert available change.
    monitor1.is_available = True
    await hass.services.async_call(
        HASS_DOMAIN, "update_entity", {ATTR_ENTITY_ID: camera1_entity_id}
    )
    await hass.async_block_till_done()

    state1 = hass.states.get(camera1_entity_id)
    assert state1.state == STATE_IDLE

    # Assert function change.
    monitor1.function = MonitorState.MONITOR
    await hass.services.async_call(
        HASS_DOMAIN, "update_entity", {ATTR_ENTITY_ID: camera1_entity_id}
    )
    await hass.async_block_till_done()

    state1 = hass.states.get(camera1_entity_id)
    assert state1.state == STATE_IDLE
    assert state1.attributes["function"] == MonitorState.MONITOR.value
    assert state1.attributes["events_all_with_archived"] == 11
    assert state1.attributes["events_all_without_archived"] == 10
    assert state1.attributes["events_hour_with_archived"] == 7
    assert state1.attributes["events_day_with_archived"] == 8
    assert state1.attributes["events_day_without_archived"] == 7
    assert state1.attributes["events_week_with_archived"] == 9
    assert state1.attributes["events_week_without_archived"] == 8
    assert state1.attributes["events_month_without_archived"] == 9
    assert "motion_detection" not in state1.attributes

    # Assert recording change.
    monitor1.is_recording = True
    await hass.services.async_call(
        HASS_DOMAIN, "update_entity", {ATTR_ENTITY_ID: camera1_entity_id}
    )
    await hass.async_block_till_done()

    state1 = hass.states.get(camera1_entity_id)
    assert state1.state == STATE_RECORDING
    assert state1.attributes["function"] == MonitorState.MONITOR.value
    assert "motion_detection" not in state1.attributes

    # Enable motion detection
    monitor1.is_recording = True
    await hass.services.async_call(
        CAMERA_DOMAIN, "enable_motion_detection", {ATTR_ENTITY_ID: camera1_entity_id}
    )
    await hass.services.async_call(
        HASS_DOMAIN, "update_entity", {ATTR_ENTITY_ID: camera1_entity_id}
    )
    await hass.async_block_till_done()

    state1 = hass.states.get(camera1_entity_id)
    assert state1.state == STATE_RECORDING
    assert state1.attributes["function"] == MonitorState.MODECT.value
    assert state1.attributes["motion_detection"] is True

    # Disable motion detection
    monitor1.is_recording = True
    await hass.services.async_call(
        CAMERA_DOMAIN, "disable_motion_detection", {ATTR_ENTITY_ID: camera1_entity_id}
    )
    await hass.services.async_call(
        HASS_DOMAIN, "update_entity", {ATTR_ENTITY_ID: camera1_entity_id}
    )
    await hass.async_block_till_done()

    state1 = hass.states.get(camera1_entity_id)
    assert state1.state == STATE_RECORDING
    assert state1.attributes["function"] == MonitorState.MONITOR.value
    assert "motion_detection" not in state1.attributes

    # Turn off
    monitor1.is_recording = True
    await hass.services.async_call(
        CAMERA_DOMAIN, "turn_off", {ATTR_ENTITY_ID: camera1_entity_id}
    )
    await hass.services.async_call(
        HASS_DOMAIN, "update_entity", {ATTR_ENTITY_ID: camera1_entity_id}
    )
    await hass.async_block_till_done()

    state1 = hass.states.get(camera1_entity_id)
    assert state1.state == STATE_RECORDING
    assert state1.attributes["function"] == MonitorState.NONE.value
    assert "motion_detection" not in state1.attributes

    # Turn on
    monitor1.is_recording = True
    await hass.services.async_call(
        CAMERA_DOMAIN, "turn_on", {ATTR_ENTITY_ID: camera1_entity_id}
    )
    await hass.services.async_call(
        HASS_DOMAIN, "update_entity", {ATTR_ENTITY_ID: camera1_entity_id}
    )
    await hass.async_block_till_done()

    state1 = hass.states.get(camera1_entity_id)
    assert state1.state == STATE_RECORDING
    assert state1.attributes["function"] == MonitorState.MONITOR.value
    assert "motion_detection" not in state1.attributes

    # Exception during update
    monitor1.get_events.side_effect = Exception("Network error.")
    await hass.services.async_call(
        HASS_DOMAIN, "update_entity", {ATTR_ENTITY_ID: camera1_entity_id}
    )
    await hass.async_block_till_done()

    state1 = hass.states.get(camera1_entity_id)
    assert state1.state == STATE_UNAVAILABLE
