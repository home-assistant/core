"""The tests for the Group components."""
# pylint: disable=protected-access
from collections import OrderedDict
import unittest

import homeassistant.components.group as group
from homeassistant.const import (
    ATTR_ASSUMED_STATE,
    ATTR_FRIENDLY_NAME,
    ATTR_ICON,
    STATE_HOME,
    STATE_NOT_HOME,
    STATE_OFF,
    STATE_ON,
    STATE_UNKNOWN,
)
from homeassistant.setup import async_setup_component, setup_component

from tests.async_mock import patch
from tests.common import assert_setup_component, get_test_home_assistant
from tests.components.group import common


class TestComponentsGroup(unittest.TestCase):
    """Test Group component."""

    # pylint: disable=invalid-name
    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()

    # pylint: disable=invalid-name
    def tearDown(self):
        """Stop everything that was started."""
        self.hass.stop()

    def test_setup_group_with_mixed_groupable_states(self):
        """Try to set up a group with mixed groupable states."""
        self.hass.states.set("light.Bowl", STATE_ON)
        self.hass.states.set("device_tracker.Paulus", STATE_HOME)
        group.Group.create_group(
            self.hass, "person_and_light", ["light.Bowl", "device_tracker.Paulus"]
        )

        assert (
            STATE_ON == self.hass.states.get(f"{group.DOMAIN}.person_and_light").state
        )

    def test_setup_group_with_a_non_existing_state(self):
        """Try to set up a group with a non existing state."""
        self.hass.states.set("light.Bowl", STATE_ON)

        grp = group.Group.create_group(
            self.hass, "light_and_nothing", ["light.Bowl", "non.existing"]
        )

        assert STATE_ON == grp.state

    def test_setup_group_with_non_groupable_states(self):
        """Test setup with groups which are not groupable."""
        self.hass.states.set("cast.living_room", "Plex")
        self.hass.states.set("cast.bedroom", "Netflix")

        grp = group.Group.create_group(
            self.hass, "chromecasts", ["cast.living_room", "cast.bedroom"]
        )

        assert STATE_UNKNOWN == grp.state

    def test_setup_empty_group(self):
        """Try to set up an empty group."""
        grp = group.Group.create_group(self.hass, "nothing", [])

        assert STATE_UNKNOWN == grp.state

    def test_monitor_group(self):
        """Test if the group keeps track of states."""
        self.hass.states.set("light.Bowl", STATE_ON)
        self.hass.states.set("light.Ceiling", STATE_OFF)
        test_group = group.Group.create_group(
            self.hass, "init_group", ["light.Bowl", "light.Ceiling"], False
        )

        # Test if group setup in our init mode is ok
        assert test_group.entity_id in self.hass.states.entity_ids()

        group_state = self.hass.states.get(test_group.entity_id)
        assert STATE_ON == group_state.state
        assert group_state.attributes.get(group.ATTR_AUTO)

    def test_group_turns_off_if_all_off(self):
        """Test if turn off if the last device that was on turns off."""
        self.hass.states.set("light.Bowl", STATE_OFF)
        self.hass.states.set("light.Ceiling", STATE_OFF)
        test_group = group.Group.create_group(
            self.hass, "init_group", ["light.Bowl", "light.Ceiling"], False
        )

        self.hass.block_till_done()

        group_state = self.hass.states.get(test_group.entity_id)
        assert STATE_OFF == group_state.state

    def test_group_turns_on_if_all_are_off_and_one_turns_on(self):
        """Test if turn on if all devices were turned off and one turns on."""
        self.hass.states.set("light.Bowl", STATE_OFF)
        self.hass.states.set("light.Ceiling", STATE_OFF)
        test_group = group.Group.create_group(
            self.hass, "init_group", ["light.Bowl", "light.Ceiling"], False
        )

        # Turn one on
        self.hass.states.set("light.Ceiling", STATE_ON)
        self.hass.block_till_done()

        group_state = self.hass.states.get(test_group.entity_id)
        assert STATE_ON == group_state.state

    def test_allgroup_stays_off_if_all_are_off_and_one_turns_on(self):
        """Group with all: true, stay off if one device turns on."""
        self.hass.states.set("light.Bowl", STATE_OFF)
        self.hass.states.set("light.Ceiling", STATE_OFF)
        test_group = group.Group.create_group(
            self.hass, "init_group", ["light.Bowl", "light.Ceiling"], False, mode=True
        )

        # Turn one on
        self.hass.states.set("light.Ceiling", STATE_ON)
        self.hass.block_till_done()

        group_state = self.hass.states.get(test_group.entity_id)
        assert STATE_OFF == group_state.state

    def test_allgroup_turn_on_if_last_turns_on(self):
        """Group with all: true, turn on if all devices are on."""
        self.hass.states.set("light.Bowl", STATE_ON)
        self.hass.states.set("light.Ceiling", STATE_OFF)
        test_group = group.Group.create_group(
            self.hass, "init_group", ["light.Bowl", "light.Ceiling"], False, mode=True
        )

        # Turn one on
        self.hass.states.set("light.Ceiling", STATE_ON)
        self.hass.block_till_done()

        group_state = self.hass.states.get(test_group.entity_id)
        assert STATE_ON == group_state.state

    def test_is_on(self):
        """Test is_on method."""
        self.hass.states.set("light.Bowl", STATE_ON)
        self.hass.states.set("light.Ceiling", STATE_OFF)
        test_group = group.Group.create_group(
            self.hass, "init_group", ["light.Bowl", "light.Ceiling"], False
        )

        assert group.is_on(self.hass, test_group.entity_id)
        self.hass.states.set("light.Bowl", STATE_OFF)
        self.hass.block_till_done()
        assert not group.is_on(self.hass, test_group.entity_id)

        # Try on non existing state
        assert not group.is_on(self.hass, "non.existing")

    def test_expand_entity_ids(self):
        """Test expand_entity_ids method."""
        self.hass.states.set("light.Bowl", STATE_ON)
        self.hass.states.set("light.Ceiling", STATE_OFF)
        test_group = group.Group.create_group(
            self.hass, "init_group", ["light.Bowl", "light.Ceiling"], False
        )

        assert sorted(["light.ceiling", "light.bowl"]) == sorted(
            group.expand_entity_ids(self.hass, [test_group.entity_id])
        )

    def test_expand_entity_ids_does_not_return_duplicates(self):
        """Test that expand_entity_ids does not return duplicates."""
        self.hass.states.set("light.Bowl", STATE_ON)
        self.hass.states.set("light.Ceiling", STATE_OFF)
        test_group = group.Group.create_group(
            self.hass, "init_group", ["light.Bowl", "light.Ceiling"], False
        )

        assert ["light.bowl", "light.ceiling"] == sorted(
            group.expand_entity_ids(self.hass, [test_group.entity_id, "light.Ceiling"])
        )

        assert ["light.bowl", "light.ceiling"] == sorted(
            group.expand_entity_ids(self.hass, ["light.bowl", test_group.entity_id])
        )

    def test_expand_entity_ids_recursive(self):
        """Test expand_entity_ids method with a group that contains itself."""
        self.hass.states.set("light.Bowl", STATE_ON)
        self.hass.states.set("light.Ceiling", STATE_OFF)
        test_group = group.Group.create_group(
            self.hass,
            "init_group",
            ["light.Bowl", "light.Ceiling", "group.init_group"],
            False,
        )

        assert sorted(["light.ceiling", "light.bowl"]) == sorted(
            group.expand_entity_ids(self.hass, [test_group.entity_id])
        )

    def test_expand_entity_ids_ignores_non_strings(self):
        """Test that non string elements in lists are ignored."""
        assert [] == group.expand_entity_ids(self.hass, [5, True])

    def test_get_entity_ids(self):
        """Test get_entity_ids method."""
        self.hass.states.set("light.Bowl", STATE_ON)
        self.hass.states.set("light.Ceiling", STATE_OFF)
        test_group = group.Group.create_group(
            self.hass, "init_group", ["light.Bowl", "light.Ceiling"], False
        )

        assert ["light.bowl", "light.ceiling"] == sorted(
            group.get_entity_ids(self.hass, test_group.entity_id)
        )

    def test_get_entity_ids_with_domain_filter(self):
        """Test if get_entity_ids works with a domain_filter."""
        self.hass.states.set("switch.AC", STATE_OFF)

        mixed_group = group.Group.create_group(
            self.hass, "mixed_group", ["light.Bowl", "switch.AC"], False
        )

        assert ["switch.ac"] == group.get_entity_ids(
            self.hass, mixed_group.entity_id, domain_filter="switch"
        )

    def test_get_entity_ids_with_non_existing_group_name(self):
        """Test get_entity_ids with a non existing group."""
        assert [] == group.get_entity_ids(self.hass, "non_existing")

    def test_get_entity_ids_with_non_group_state(self):
        """Test get_entity_ids with a non group state."""
        assert [] == group.get_entity_ids(self.hass, "switch.AC")

    def test_group_being_init_before_first_tracked_state_is_set_to_on(self):
        """Test if the groups turn on.

        If no states existed and now a state it is tracking is being added
        as ON.
        """
        test_group = group.Group.create_group(
            self.hass, "test group", ["light.not_there_1"]
        )

        self.hass.states.set("light.not_there_1", STATE_ON)

        self.hass.block_till_done()

        group_state = self.hass.states.get(test_group.entity_id)
        assert STATE_ON == group_state.state

    def test_group_being_init_before_first_tracked_state_is_set_to_off(self):
        """Test if the group turns off.

        If no states existed and now a state it is tracking is being added
        as OFF.
        """
        test_group = group.Group.create_group(
            self.hass, "test group", ["light.not_there_1"]
        )

        self.hass.states.set("light.not_there_1", STATE_OFF)

        self.hass.block_till_done()

        group_state = self.hass.states.get(test_group.entity_id)
        assert STATE_OFF == group_state.state

    def test_setup(self):
        """Test setup method."""
        self.hass.states.set("light.Bowl", STATE_ON)
        self.hass.states.set("light.Ceiling", STATE_OFF)
        test_group = group.Group.create_group(
            self.hass, "init_group", ["light.Bowl", "light.Ceiling"], False
        )

        group_conf = OrderedDict()
        group_conf["second_group"] = {
            "entities": f"light.Bowl, {test_group.entity_id}",
            "icon": "mdi:work",
        }
        group_conf["test_group"] = "hello.world,sensor.happy"
        group_conf["empty_group"] = {"name": "Empty Group", "entities": None}

        setup_component(self.hass, "group", {"group": group_conf})

        group_state = self.hass.states.get(f"{group.DOMAIN}.second_group")
        assert STATE_ON == group_state.state
        assert {test_group.entity_id, "light.bowl"} == set(
            group_state.attributes["entity_id"]
        )
        assert group_state.attributes.get(group.ATTR_AUTO) is None
        assert "mdi:work" == group_state.attributes.get(ATTR_ICON)
        assert 1 == group_state.attributes.get(group.ATTR_ORDER)

        group_state = self.hass.states.get(f"{group.DOMAIN}.test_group")
        assert STATE_UNKNOWN == group_state.state
        assert {"sensor.happy", "hello.world"} == set(
            group_state.attributes["entity_id"]
        )
        assert group_state.attributes.get(group.ATTR_AUTO) is None
        assert group_state.attributes.get(ATTR_ICON) is None
        assert 2 == group_state.attributes.get(group.ATTR_ORDER)

    def test_groups_get_unique_names(self):
        """Two groups with same name should both have a unique entity id."""
        grp1 = group.Group.create_group(self.hass, "Je suis Charlie")
        grp2 = group.Group.create_group(self.hass, "Je suis Charlie")

        assert grp1.entity_id != grp2.entity_id

    def test_expand_entity_ids_expands_nested_groups(self):
        """Test if entity ids epands to nested groups."""
        group.Group.create_group(self.hass, "light", ["light.test_1", "light.test_2"])
        group.Group.create_group(
            self.hass, "switch", ["switch.test_1", "switch.test_2"]
        )
        group.Group.create_group(
            self.hass, "group_of_groups", ["group.light", "group.switch"]
        )

        assert [
            "light.test_1",
            "light.test_2",
            "switch.test_1",
            "switch.test_2",
        ] == sorted(group.expand_entity_ids(self.hass, ["group.group_of_groups"]))

    def test_set_assumed_state_based_on_tracked(self):
        """Test assumed state."""
        self.hass.states.set("light.Bowl", STATE_ON)
        self.hass.states.set("light.Ceiling", STATE_OFF)
        test_group = group.Group.create_group(
            self.hass, "init_group", ["light.Bowl", "light.Ceiling", "sensor.no_exist"]
        )

        state = self.hass.states.get(test_group.entity_id)
        assert not state.attributes.get(ATTR_ASSUMED_STATE)

        self.hass.states.set("light.Bowl", STATE_ON, {ATTR_ASSUMED_STATE: True})
        self.hass.block_till_done()

        state = self.hass.states.get(test_group.entity_id)
        assert state.attributes.get(ATTR_ASSUMED_STATE)

        self.hass.states.set("light.Bowl", STATE_ON)
        self.hass.block_till_done()

        state = self.hass.states.get(test_group.entity_id)
        assert not state.attributes.get(ATTR_ASSUMED_STATE)

    def test_group_updated_after_device_tracker_zone_change(self):
        """Test group state when device tracker in group changes zone."""
        self.hass.states.set("device_tracker.Adam", STATE_HOME)
        self.hass.states.set("device_tracker.Eve", STATE_NOT_HOME)
        self.hass.block_till_done()
        group.Group.create_group(
            self.hass, "peeps", ["device_tracker.Adam", "device_tracker.Eve"]
        )
        self.hass.states.set("device_tracker.Adam", "cool_state_not_home")
        self.hass.block_till_done()
        assert STATE_NOT_HOME == self.hass.states.get(f"{group.DOMAIN}.peeps").state

    def test_reloading_groups(self):
        """Test reloading the group config."""
        assert setup_component(
            self.hass,
            "group",
            {
                "group": {
                    "second_group": {"entities": "light.Bowl", "icon": "mdi:work"},
                    "test_group": "hello.world,sensor.happy",
                    "empty_group": {"name": "Empty Group", "entities": None},
                }
            },
        )

        group.Group.create_group(
            self.hass, "all tests", ["test.one", "test.two"], user_defined=False
        )

        assert sorted(self.hass.states.entity_ids()) == [
            "group.all_tests",
            "group.empty_group",
            "group.second_group",
            "group.test_group",
        ]
        assert self.hass.bus.listeners["state_changed"] == 3

        with patch(
            "homeassistant.config.load_yaml_config_file",
            return_value={
                "group": {"hello": {"entities": "light.Bowl", "icon": "mdi:work"}}
            },
        ):
            common.reload(self.hass)
            self.hass.block_till_done()

        assert sorted(self.hass.states.entity_ids()) == [
            "group.all_tests",
            "group.hello",
        ]
        assert self.hass.bus.listeners["state_changed"] == 2

    def test_modify_group(self):
        """Test modifying a group."""
        group_conf = OrderedDict()
        group_conf["modify_group"] = {"name": "friendly_name", "icon": "mdi:work"}

        assert setup_component(self.hass, "group", {"group": group_conf})

        # The old way would create a new group modify_group1 because
        # internally it didn't know anything about those created in the config
        common.set_group(self.hass, "modify_group", icon="mdi:play")
        self.hass.block_till_done()

        group_state = self.hass.states.get(f"{group.DOMAIN}.modify_group")

        assert self.hass.states.entity_ids() == ["group.modify_group"]
        assert group_state.attributes.get(ATTR_ICON) == "mdi:play"
        assert group_state.attributes.get(ATTR_FRIENDLY_NAME) == "friendly_name"


async def test_service_group_services(hass):
    """Check if service are available."""
    with assert_setup_component(0, "group"):
        await async_setup_component(hass, "group", {"group": {}})

    assert hass.services.has_service("group", group.SERVICE_SET)
    assert hass.services.has_service("group", group.SERVICE_REMOVE)


# pylint: disable=invalid-name
async def test_service_group_set_group_remove_group(hass):
    """Check if service are available."""
    with assert_setup_component(0, "group"):
        await async_setup_component(hass, "group", {"group": {}})

    common.async_set_group(hass, "user_test_group", name="Test")
    await hass.async_block_till_done()

    group_state = hass.states.get("group.user_test_group")
    assert group_state
    assert group_state.attributes[group.ATTR_AUTO]
    assert group_state.attributes["friendly_name"] == "Test"

    common.async_set_group(hass, "user_test_group", entity_ids=["test.entity_bla1"])
    await hass.async_block_till_done()

    group_state = hass.states.get("group.user_test_group")
    assert group_state
    assert group_state.attributes[group.ATTR_AUTO]
    assert group_state.attributes["friendly_name"] == "Test"
    assert list(group_state.attributes["entity_id"]) == ["test.entity_bla1"]

    common.async_set_group(
        hass,
        "user_test_group",
        icon="mdi:camera",
        name="Test2",
        add=["test.entity_id2"],
    )
    await hass.async_block_till_done()

    group_state = hass.states.get("group.user_test_group")
    assert group_state
    assert group_state.attributes[group.ATTR_AUTO]
    assert group_state.attributes["friendly_name"] == "Test2"
    assert group_state.attributes["icon"] == "mdi:camera"
    assert sorted(list(group_state.attributes["entity_id"])) == sorted(
        ["test.entity_bla1", "test.entity_id2"]
    )

    common.async_remove(hass, "user_test_group")
    await hass.async_block_till_done()

    group_state = hass.states.get("group.user_test_group")
    assert group_state is None
