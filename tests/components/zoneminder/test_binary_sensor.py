"""Binary sensor tests."""
from zoneminder.zm import ZoneMinder

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
)
from homeassistant.core import DOMAIN as HASS_DOMAIN, HomeAssistant
from homeassistant.setup import async_setup_component

from tests.async_mock import MagicMock, patch
from tests.common import MockConfigEntry


@patch("homeassistant.components.zoneminder.common.ZoneMinder", autospec=ZoneMinder)
async def test_async_setup_entry(zoneminder_mock, hass: HomeAssistant) -> None:
    """Test setup of binary sensor entities."""
    zm_client: ZoneMinder = MagicMock(spec=ZoneMinder)
    zm_client.get_zms_url.return_value = "http://host1/path_zms1"
    zm_client.login.return_value = True
    zm_client.is_available = True

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

    await hass.services.async_call(
        HASS_DOMAIN, "update_entity", {ATTR_ENTITY_ID: "binary_sensor.host1"}
    )
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.host1").state == "on"

    zm_client.is_available = False
    await hass.services.async_call(
        HASS_DOMAIN, "update_entity", {ATTR_ENTITY_ID: "binary_sensor.host1"}
    )
    await hass.async_block_till_done()
    assert hass.states.get("binary_sensor.host1").state == "off"
