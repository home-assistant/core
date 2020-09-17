"""Binary sensor tests."""
from zoneminder.monitor import Monitor, MonitorState
from zoneminder.zm import ZoneMinder

from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.zoneminder import const
from homeassistant.config import async_process_ha_core_config
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_COMMAND_OFF,
    CONF_COMMAND_ON,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_PLATFORM,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    STATE_OFF,
    STATE_ON,
)
from homeassistant.core import DOMAIN as HASS_DOMAIN, HomeAssistant
from homeassistant.setup import async_setup_component

from tests.async_mock import MagicMock, patch
from tests.common import MockConfigEntry


async def test_async_setup_entry(hass: HomeAssistant) -> None:
    """Test setup of sensor entities."""

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

        monitor2 = MagicMock(spec=Monitor)
        monitor2.name = "monitor2"
        monitor2.mjpeg_image_url = "mjpeg_image_url2"
        monitor2.still_image_url = "still_image_url2"
        monitor2.is_recording = False
        monitor2.is_available = False
        monitor2.function = MonitorState.MODECT

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
            SWITCH_DOMAIN: [
                {
                    CONF_PLATFORM: const.DOMAIN,
                    CONF_COMMAND_ON: MonitorState.MONITOR.value,
                    CONF_COMMAND_OFF: MonitorState.MODECT.value,
                },
                {
                    CONF_PLATFORM: const.DOMAIN,
                    CONF_COMMAND_ON: MonitorState.MODECT.value,
                    CONF_COMMAND_OFF: MonitorState.MONITOR.value,
                },
            ],
        }

        await async_process_ha_core_config(hass, hass_config[HASS_DOMAIN])
        await async_setup_component(hass, HASS_DOMAIN, hass_config)
        await async_setup_component(hass, SWITCH_DOMAIN, hass_config)
        await hass.async_block_till_done()
        await async_setup_component(hass, const.DOMAIN, hass_config)
        await hass.async_block_till_done()

        await hass.services.async_call(
            SWITCH_DOMAIN, "turn_on", {ATTR_ENTITY_ID: "switch.monitor1_state"}
        )
        await hass.services.async_call(
            SWITCH_DOMAIN, "turn_off", {ATTR_ENTITY_ID: "switch.monitor1_state_2"}
        )
        await hass.async_block_till_done()
        assert hass.states.get("switch.monitor1_state").state == STATE_ON
        assert hass.states.get("switch.monitor1_state_2").state == STATE_OFF

        await hass.services.async_call(
            SWITCH_DOMAIN, "turn_off", {ATTR_ENTITY_ID: "switch.monitor1_state"}
        )
        await hass.services.async_call(
            SWITCH_DOMAIN, "turn_on", {ATTR_ENTITY_ID: "switch.monitor1_state_2"}
        )
        await hass.async_block_till_done()
        assert hass.states.get("switch.monitor1_state").state == STATE_OFF
        assert hass.states.get("switch.monitor1_state_2").state == STATE_ON

        monitor1.function = MonitorState.NONE
        monitor2.function = MonitorState.NODECT
        await hass.services.async_call(
            HASS_DOMAIN, "update_entity", {ATTR_ENTITY_ID: "switch.monitor1_state"}
        )
        await hass.services.async_call(
            HASS_DOMAIN, "update_entity", {ATTR_ENTITY_ID: "switch.monitor1_state_2"}
        )
        await hass.async_block_till_done()
        assert hass.states.get("switch.monitor1_state").state == STATE_OFF
        assert hass.states.get("switch.monitor1_state_2").state == STATE_OFF
