"""Binary sensor tests."""
from zoneminder.monitor import Monitor, MonitorState, TimePeriod
from zoneminder.zm import ZoneMinder

from homeassistant.components.homeassistant import SERVICE_UPDATE_ENTITY
from homeassistant.components.zoneminder import async_setup_entry
from homeassistant.components.zoneminder.const import CONF_PATH_ZMS, DOMAIN
from homeassistant.components.zoneminder.sensor import ZMSensorEvents
from homeassistant.const import (
    ATTR_ENTITY_ID,
    CONF_HOST,
    CONF_PASSWORD,
    CONF_PATH,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
    STATE_UNAVAILABLE,
)
from homeassistant.core import DOMAIN as HASS_DOMAIN, HomeAssistant
from homeassistant.setup import async_setup_component
from homeassistant.util import slugify

from tests.async_mock import MagicMock, PropertyMock, patch
from tests.common import MockConfigEntry


@patch("homeassistant.components.zoneminder.common.ZoneMinder", autospec=ZoneMinder)
async def test_monitor_state(zoneminder_mock, hass: HomeAssistant) -> None:
    """Test setup of sensor entities."""

    entity_id = "sensor.zoneminder_camera1_status"

    function_property = PropertyMock(return_value=MonitorState.NONE)

    monitor: Monitor = MagicMock(spec=Monitor)
    monitor.name = "camera1"
    type(monitor).function = function_property
    monitor.is_available = False

    zm_client: ZoneMinder = MagicMock(spec=ZoneMinder)
    zm_client.get_zms_url.return_value = "http://host1/path_zms1"
    zm_client.login.return_value = True
    zm_client.get_monitors.return_value = [monitor]
    zm_client.get_active_state.return_value = "Home"
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

    state = hass.states.get(entity_id)
    assert state.state == STATE_UNAVAILABLE

    monitor.is_available = True
    await hass.services.async_call(
        HASS_DOMAIN, SERVICE_UPDATE_ENTITY, {ATTR_ENTITY_ID: entity_id}
    )
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == MonitorState.NONE.value

    function_property.return_value = MonitorState.MONITOR
    await hass.services.async_call(
        HASS_DOMAIN, SERVICE_UPDATE_ENTITY, {ATTR_ENTITY_ID: entity_id}
    )
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == MonitorState.MONITOR.value

    function_property.side_effect = Exception("Network error")
    await hass.services.async_call(
        HASS_DOMAIN, SERVICE_UPDATE_ENTITY, {ATTR_ENTITY_ID: entity_id}
    )
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_UNAVAILABLE

    function_property.side_effect = None
    function_property.return_value = MonitorState.MODECT
    await hass.services.async_call(
        HASS_DOMAIN, SERVICE_UPDATE_ENTITY, {ATTR_ENTITY_ID: entity_id}
    )
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == MonitorState.MODECT.value


@patch("homeassistant.components.zoneminder.common.ZoneMinder", autospec=ZoneMinder)
async def test_sensor_events_disabled_by_default(
    zoneminder_mock, hass: HomeAssistant
) -> None:
    """Test setup of sensor entities."""

    monitor: Monitor = MagicMock(spec=Monitor)
    monitor.name = "camera1"
    monitor.is_available = True

    zm_client: ZoneMinder = MagicMock(spec=ZoneMinder)
    zm_client.get_zms_url.return_value = "http://host1/path_zms1"
    zm_client.login.return_value = True
    zm_client.get_monitors.return_value = [monitor]
    zm_client.get_active_state.return_value = "Home"
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

    # Hidden by default
    for time_period in TimePeriod:
        for include_archived in (True, False):
            archived_name = "with_archived" if include_archived else "without_archived"
            entity_id = (
                f"sensor.zoneminder_camera1_events_{time_period.value}_{archived_name}"
            )

            assert not hass.states.get(entity_id)


@patch(
    "homeassistant.components.zoneminder.sensor.ZMSensorEvents.entity_registry_enabled_default"
)
@patch("homeassistant.components.zoneminder.common.ZoneMinder", autospec=ZoneMinder)
async def test_sensor_events_enabled(
    zoneminder_mock, enabled_by_default_mock, hass: HomeAssistant
) -> None:
    """Test setup of sensor entities."""

    enabled_by_default_mock.return_value = True

    data = {
        TimePeriod.HOUR: {True: 10, False: 11},
        TimePeriod.DAY: {True: 20, False: 21},
        TimePeriod.WEEK: {True: 20, False: 31},
        TimePeriod.MONTH: {True: 40, False: 41},
        TimePeriod.ALL: {True: 50, False: 51},
    }

    def get_events(time_period: TimePeriod, include_archived: bool) -> int:
        return data[time_period][include_archived]

    monitor: Monitor = MagicMock(spec=Monitor)
    monitor.name = "camera1"
    monitor.is_available = True
    monitor.get_events.side_effect = get_events

    zm_client: ZoneMinder = MagicMock(spec=ZoneMinder)
    zm_client.get_zms_url.return_value = "http://host1/path_zms1"
    zm_client.login.return_value = True
    zm_client.get_monitors.return_value = [monitor]
    zm_client.get_active_state.return_value = "Home"
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

    for time_period in data:
        for include_archived in data[time_period]:
            count = data[time_period][include_archived]
            entity_id = "sensor." + slugify(
                ZMSensorEvents.get_name(monitor.name, time_period, include_archived)
            )

            await hass.services.async_call(
                HASS_DOMAIN, SERVICE_UPDATE_ENTITY, {ATTR_ENTITY_ID: entity_id}
            )
            await hass.async_block_till_done()

            assert hass.states.get(entity_id).state == str(count)

    monitor.get_events.side_effect = Exception("Network error")
    for time_period in data:
        for include_archived in data[time_period]:
            entity_id = "sensor." + slugify(
                ZMSensorEvents.get_name(monitor.name, time_period, include_archived)
            )

            await hass.services.async_call(
                HASS_DOMAIN, SERVICE_UPDATE_ENTITY, {ATTR_ENTITY_ID: entity_id}
            )
            await hass.async_block_till_done()

            assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


@patch("homeassistant.components.zoneminder.common.ZoneMinder", autospec=ZoneMinder)
async def test_run_state(zoneminder_mock, hass: HomeAssistant) -> None:
    """Test setup of sensor entities."""

    entity_id = "sensor.zoneminder_run_state"

    zm_client: ZoneMinder = MagicMock(spec=ZoneMinder)
    zm_client.get_zms_url.return_value = "http://host1/path_zms1"
    zm_client.login.return_value = True
    zm_client.get_monitors.return_value = []
    zm_client.get_active_state.return_value = "Home"
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
        HASS_DOMAIN, SERVICE_UPDATE_ENTITY, {ATTR_ENTITY_ID: entity_id}
    )
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == "Home"
    assert state.attributes[CONF_HOST] == "host1"

    zm_client.get_active_state.return_value = "Away"
    await hass.services.async_call(
        HASS_DOMAIN, SERVICE_UPDATE_ENTITY, {ATTR_ENTITY_ID: entity_id}
    )
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == "Away"
    assert state.attributes[CONF_HOST] == "host1"

    zm_client.get_active_state.side_effect = Exception("Network error")
    await hass.services.async_call(
        HASS_DOMAIN, SERVICE_UPDATE_ENTITY, {ATTR_ENTITY_ID: entity_id}
    )
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == STATE_UNAVAILABLE

    zm_client.get_active_state.side_effect = None
    zm_client.get_active_state.return_value = "Away"
    await hass.services.async_call(
        HASS_DOMAIN, SERVICE_UPDATE_ENTITY, {ATTR_ENTITY_ID: entity_id}
    )
    await hass.async_block_till_done()
    state = hass.states.get(entity_id)
    assert state.state == "Away"
    assert state.attributes[CONF_HOST] == "host1"
