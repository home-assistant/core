"""Binary sensor tests."""
from zoneminder.monitor import Monitor
from zoneminder.zm import ZoneMinder

from homeassistant.components.zoneminder import const
from homeassistant.config import async_process_ha_core_config
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import DOMAIN as HASS_DOMAIN, HomeAssistant
from homeassistant.setup import async_setup_component

from tests.async_mock import MagicMock, patch
from tests.common import MockConfigEntry


async def test_async_setup_entry(hass: HomeAssistant) -> None:
    """Test setup of camera entities."""
    with patch(
        "homeassistant.components.zoneminder.common.ZoneMinder", autospec=ZoneMinder
    ) as zoneminder_mock:
        monitor1 = MagicMock(spec=Monitor)
        monitor1.name = "monitor1"
        monitor1.mjpeg_image_url = "mjpeg_image_url1"
        monitor1.still_image_url = "still_image_url1"
        monitor1.is_recording = True
        monitor1.is_available = True

        monitor2 = MagicMock(spec=Monitor)
        monitor2.name = "monitor2"
        monitor2.mjpeg_image_url = "mjpeg_image_url2"
        monitor2.still_image_url = "still_image_url2"
        monitor2.is_recording = False
        monitor2.is_available = False

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

        await async_process_ha_core_config(hass, {})
        await async_setup_component(hass, HASS_DOMAIN, {})
        await async_setup_component(hass, const.DOMAIN, {})
        await hass.async_block_till_done()

        await hass.services.async_call(
            HASS_DOMAIN, "update_entity", {ATTR_ENTITY_ID: "camera.monitor1"}
        )
        await hass.services.async_call(
            HASS_DOMAIN, "update_entity", {ATTR_ENTITY_ID: "camera.monitor2"}
        )
        await hass.async_block_till_done()
        assert hass.states.get("camera.monitor1").state == "recording"
        assert hass.states.get("camera.monitor2").state == "unavailable"

        monitor1.is_recording = False
        monitor2.is_recording = True
        await hass.services.async_call(
            HASS_DOMAIN, "update_entity", {ATTR_ENTITY_ID: "camera.monitor1"}
        )
        await hass.services.async_call(
            HASS_DOMAIN, "update_entity", {ATTR_ENTITY_ID: "camera.monitor2"}
        )
        await hass.async_block_till_done()
        assert hass.states.get("camera.monitor1").state == "idle"
        assert hass.states.get("camera.monitor2").state == "unavailable"
