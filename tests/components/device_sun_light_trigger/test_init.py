"""The tests device sun light trigger component."""
# pylint: disable=protected-access
from datetime import datetime

from asynctest import patch
import pytest

from homeassistant.components import (
    device_sun_light_trigger,
    device_tracker,
    group,
    light,
)
from homeassistant.components.device_tracker.const import (
    ENTITY_ID_FORMAT as DT_ENTITY_ID_FORMAT,
)
from homeassistant.const import CONF_PLATFORM, STATE_HOME, STATE_NOT_HOME
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util

from tests.common import async_fire_time_changed
from tests.components.light import common as common_light


@pytest.fixture
def scanner(hass):
    """Initialize components."""
    scanner = getattr(hass.components, "test.device_tracker").get_scanner(None, None)

    scanner.reset()
    scanner.come_home("DEV1")

    getattr(hass.components, "test.light").init()

    with patch(
        "homeassistant.components.device_tracker.legacy.load_yaml_config_file",
        return_value={
            "device_1": {
                "hide_if_away": False,
                "mac": "DEV1",
                "name": "Unnamed Device",
                "picture": "http://example.com/dev1.jpg",
                "track": True,
                "vendor": None,
            },
            "device_2": {
                "hide_if_away": False,
                "mac": "DEV2",
                "name": "Unnamed Device",
                "picture": "http://example.com/dev2.jpg",
                "track": True,
                "vendor": None,
            },
        },
    ):
        assert hass.loop.run_until_complete(
            async_setup_component(
                hass,
                device_tracker.DOMAIN,
                {device_tracker.DOMAIN: {CONF_PLATFORM: "test"}},
            )
        )

    assert hass.loop.run_until_complete(
        async_setup_component(
            hass, light.DOMAIN, {light.DOMAIN: {CONF_PLATFORM: "test"}}
        )
    )

    return scanner


async def test_lights_on_when_sun_sets(hass, scanner):
    """Test lights go on when there is someone home and the sun sets."""
    test_time = datetime(2017, 4, 5, 1, 2, 3, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=test_time):
        assert await async_setup_component(
            hass, device_sun_light_trigger.DOMAIN, {device_sun_light_trigger.DOMAIN: {}}
        )

    await common_light.async_turn_off(hass)

    test_time = test_time.replace(hour=3)
    with patch("homeassistant.util.dt.utcnow", return_value=test_time):
        async_fire_time_changed(hass, test_time)
        await hass.async_block_till_done()

    assert all(
        light.is_on(hass, ent_id) for ent_id in hass.states.async_entity_ids("light")
    )


async def test_lights_turn_off_when_everyone_leaves(hass):
    """Test lights turn off when everyone leaves the house."""
    assert await async_setup_component(
        hass, "light", {light.DOMAIN: {CONF_PLATFORM: "test"}}
    )
    await common_light.async_turn_on(hass)
    hass.states.async_set("device_tracker.bla", STATE_HOME)

    assert await async_setup_component(
        hass, device_sun_light_trigger.DOMAIN, {device_sun_light_trigger.DOMAIN: {}}
    )

    hass.states.async_set("device_tracker.bla", STATE_NOT_HOME)

    await hass.async_block_till_done()

    assert all(
        not light.is_on(hass, ent_id)
        for ent_id in hass.states.async_entity_ids("light")
    )


async def test_lights_turn_on_when_coming_home_after_sun_set(hass, scanner):
    """Test lights turn on when coming home after sun set."""
    test_time = datetime(2017, 4, 5, 3, 2, 3, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=test_time):
        await common_light.async_turn_off(hass)

        assert await async_setup_component(
            hass, device_sun_light_trigger.DOMAIN, {device_sun_light_trigger.DOMAIN: {}}
        )

        hass.states.async_set(DT_ENTITY_ID_FORMAT.format("device_2"), STATE_HOME)

        await hass.async_block_till_done()

    assert all(
        light.is_on(hass, ent_id) for ent_id in hass.states.async_entity_ids("light")
    )


async def test_lights_turn_on_when_coming_home_after_sun_set_person(hass, scanner):
    """Test lights turn on when coming home after sun set."""
    device_1 = DT_ENTITY_ID_FORMAT.format("device_1")
    device_2 = DT_ENTITY_ID_FORMAT.format("device_2")

    test_time = datetime(2017, 4, 5, 3, 2, 3, tzinfo=dt_util.UTC)
    with patch("homeassistant.util.dt.utcnow", return_value=test_time):
        await common_light.async_turn_off(hass)
        hass.states.async_set(device_1, STATE_NOT_HOME)
        hass.states.async_set(device_2, STATE_NOT_HOME)
        await hass.async_block_till_done()

        assert all(
            not light.is_on(hass, ent_id)
            for ent_id in hass.states.async_entity_ids("light")
        )
        assert hass.states.get(device_1).state == "not_home"
        assert hass.states.get(device_2).state == "not_home"

        assert await async_setup_component(
            hass,
            "person",
            {"person": [{"id": "me", "name": "Me", "device_trackers": [device_1]}]},
        )

        await group.Group.async_create_group(hass, "person_me", ["person.me"])

        assert await async_setup_component(
            hass,
            device_sun_light_trigger.DOMAIN,
            {device_sun_light_trigger.DOMAIN: {"device_group": "group.person_me"}},
        )

        assert all(
            not light.is_on(hass, ent_id)
            for ent_id in hass.states.async_entity_ids("light")
        )
        assert hass.states.get(device_1).state == "not_home"
        assert hass.states.get(device_2).state == "not_home"
        assert hass.states.get("person.me").state == "not_home"

        # Unrelated device has no impact
        hass.states.async_set(device_2, STATE_HOME)
        await hass.async_block_till_done()

        assert all(
            not light.is_on(hass, ent_id)
            for ent_id in hass.states.async_entity_ids("light")
        )
        assert hass.states.get(device_1).state == "not_home"
        assert hass.states.get(device_2).state == "home"
        assert hass.states.get("person.me").state == "not_home"

        # person home switches on
        hass.states.async_set(device_1, STATE_HOME)
        await hass.async_block_till_done()
        await hass.async_block_till_done()

        assert all(
            light.is_on(hass, ent_id)
            for ent_id in hass.states.async_entity_ids("light")
        )
        assert hass.states.get(device_1).state == "home"
        assert hass.states.get(device_2).state == "home"
        assert hass.states.get("person.me").state == "home"
