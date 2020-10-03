"""Binary sensor tests."""
from zoneminder.monitor import Monitor, MonitorState
from zoneminder.zm import ZoneMinder

from homeassistant.components.homeassistant import SERVICE_UPDATE_ENTITY
from homeassistant.components.switch import DOMAIN as SWITCH_DOMAIN
from homeassistant.components.zoneminder import CONF_PATH_ZMS, DOMAIN, async_setup_entry
from homeassistant.components.zoneminder.switch import ZMSwitchMonitors
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    SERVICE_TURN_OFF,
    SERVICE_TURN_ON,
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
)
from homeassistant.core import DOMAIN as HASS_DOMAIN, HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import slugify

from tests.async_mock import MagicMock, PropertyMock, patch
from tests.common import MockConfigEntry


@patch("homeassistant.components.zoneminder.common.ZoneMinder", autospec=ZoneMinder)
async def test_switch_monitor_disabled_by_default(
    zoneminder_mock, hass: HomeAssistant
) -> None:
    """Test setup of sensor entities."""

    monitor = MagicMock(spec=Monitor)
    monitor.name = "monitor1"
    monitor.mjpeg_image_url = "mjpeg_image_url1"
    monitor.still_image_url = "still_image_url1"
    monitor.is_recording = True
    monitor.is_available = True
    monitor.function = MonitorState.MONITOR

    zm_client: ZoneMinder = MagicMock(spec=ZoneMinder)
    zm_client.get_zms_url.return_value = "http://host1/path_zms1"
    zm_client.login.return_value = True
    zm_client.get_monitors.return_value = [monitor]

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

    # Hidden by default
    for on_state in MonitorState:
        for off_state in MonitorState:
            entity_id = "switch." + slugify(
                ZMSwitchMonitors.get_name(monitor.name, on_state, off_state)
            )
            assert not hass.states.get(entity_id)


@patch(
    "homeassistant.components.zoneminder.switch.ZMSwitchMonitors.entity_registry_enabled_default"
)
@patch("homeassistant.components.zoneminder.common.ZoneMinder", autospec=ZoneMinder)
async def test_switch_monitor_update(
    zoneminder_mock, enabled_by_default_mock, hass: HomeAssistant
) -> None:
    """Test setup of sensor entities."""

    enabled_by_default_mock.return_value = True

    function_property = PropertyMock(return_value=MonitorState.MONITOR)

    monitor = MagicMock(spec=Monitor)
    monitor.name = "monitor1"
    monitor.mjpeg_image_url = "mjpeg_image_url1"
    monitor.still_image_url = "still_image_url1"
    monitor.is_recording = True
    monitor.is_available = True
    type(monitor).function = function_property

    zm_client: ZoneMinder = MagicMock(spec=ZoneMinder)
    zm_client.get_zms_url.return_value = "http://host1/path_zms1"
    zm_client.login.return_value = True
    zm_client.get_monitors.return_value = [monitor]

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

    # Same states should not exist.
    for on_state in MonitorState:
        for off_state in MonitorState:
            entity_id = slugify(
                ZMSwitchMonitors.get_name(monitor.name, on_state, off_state)
            )

            if on_state == off_state:
                assert not hass.states.get(entity_id)

    entity_id = "switch." + slugify(
        ZMSwitchMonitors.get_name(
            monitor.name, MonitorState.MONITOR, MonitorState.MODECT
        )
    )

    function_property.return_value = MonitorState.MONITOR
    await hass.services.async_call(
        HASS_DOMAIN, SERVICE_UPDATE_ENTITY, {ATTR_ENTITY_ID: entity_id}
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_ON

    function_property.return_value = MonitorState.NONE
    await hass.services.async_call(
        HASS_DOMAIN, SERVICE_UPDATE_ENTITY, {ATTR_ENTITY_ID: entity_id}
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_OFF

    function_property.return_value = MonitorState.NODECT
    await hass.services.async_call(
        HASS_DOMAIN, SERVICE_UPDATE_ENTITY, {ATTR_ENTITY_ID: entity_id}
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_OFF

    function_property.return_value = MonitorState.MONITOR
    await hass.services.async_call(
        HASS_DOMAIN, SERVICE_UPDATE_ENTITY, {ATTR_ENTITY_ID: entity_id}
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_ON

    function_property.side_effect = Exception("Network error")
    await hass.services.async_call(
        HASS_DOMAIN, SERVICE_UPDATE_ENTITY, {ATTR_ENTITY_ID: entity_id}
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE

    function_property.side_effect = None
    await hass.services.async_call(
        HASS_DOMAIN, SERVICE_UPDATE_ENTITY, {ATTR_ENTITY_ID: entity_id}
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_ON


@patch(
    "homeassistant.components.zoneminder.switch.ZMSwitchMonitors.entity_registry_enabled_default"
)
@patch("homeassistant.components.zoneminder.common.ZoneMinder", autospec=ZoneMinder)
async def test_switch_monitor_turn_on_off(
    zoneminder_mock, enabled_by_default_mock, hass: HomeAssistant
) -> None:
    """Test setup of sensor entities."""

    enabled_by_default_mock.return_value = True

    monitor = MagicMock(spec=Monitor)
    monitor.name = "monitor1"
    monitor.mjpeg_image_url = "mjpeg_image_url1"
    monitor.still_image_url = "still_image_url1"
    monitor.is_recording = True
    monitor.is_available = True
    monitor.function = MonitorState.MONITOR

    zm_client: ZoneMinder = MagicMock(spec=ZoneMinder)
    zm_client.get_zms_url.return_value = "http://host1/path_zms1"
    zm_client.login.return_value = True
    zm_client.get_monitors.return_value = [monitor]

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

    # Same states should not exist.
    for on_state in MonitorState:
        for off_state in MonitorState:
            entity_id = slugify(
                ZMSwitchMonitors.get_name(monitor.name, on_state, off_state)
            )

            if on_state == off_state:
                assert not hass.states.get(entity_id)

    entity_id = "switch." + slugify(
        ZMSwitchMonitors.get_name(
            monitor.name, MonitorState.MONITOR, MonitorState.MODECT
        )
    )

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_ON
    assert monitor.function == MonitorState.MONITOR

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_OFF, {ATTR_ENTITY_ID: entity_id}
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_OFF
    assert monitor.function == MonitorState.MODECT

    await hass.services.async_call(
        SWITCH_DOMAIN, SERVICE_TURN_ON, {ATTR_ENTITY_ID: entity_id}
    )
    await hass.async_block_till_done()
    assert hass.states.get(entity_id).state == STATE_ON
    assert monitor.function == MonitorState.MONITOR
