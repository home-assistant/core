"""The tests for the local_git component."""
import unittest
from unittest.mock import Mock

from homeassistant.const import (STATE_UNKNOWN)

from homeassistant.components.version_control import local_git as local_git
from homeassistant.setup import setup_component
from tests.common import (get_test_home_assistant, MockDependency)

TEST_CONFIG = {
    'version_control': {
        'platform': 'local_git',
        local_git.CONF_NAME: 'test_name',
        local_git.CONF_PATH: 'test_path'
    }
}

TEST_BRANCH_NAME = 'master'
TEST_COMMIT_HEXSHA = 'test_hexsha'
TEST_COMMIT_TITLE = 'test_summary'


class TestLocalGit(unittest.TestCase):
    """Test the local_git platform."""

    def setUp(self):
        """Initialize values for this test case class."""
        self.hass = get_test_home_assistant()
        self.config = TEST_CONFIG

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that we started."""
        self.hass.stop()

    @MockDependency('git')
    def test_setup_platform(self, mock_git):
        """Test successful setup."""
        self.assertTrue(
            setup_component(self.hass, 'version_control', TEST_CONFIG)
        )

        add_devices = Mock()
        local_git.setup_platform(
            self.hass, TEST_CONFIG['version_control'], add_devices
        )

        self.assertTrue(add_devices.called)
        self.assertTrue(
            isinstance(
                add_devices.call_args[0][0][0],
                local_git.GitRepo)
        )
        self.assertEqual(1, len(self.hass.states.all()))

    def test_valid_gitrepo_values(self):
        """Test valid GitRepo values."""
        entity = self._createTestEntity(
            is_bare=False,
            is_valid=True,
            is_dirty=False
        )

        self.assertEqual(STATE_UNKNOWN, entity.state)

        entity.update()

        self.assertEqual(
            "{}".format(
                TEST_CONFIG['version_control'][local_git.CONF_NAME]
            ),
            entity.name
        )
        self.assertEqual(TEST_COMMIT_HEXSHA, entity.state)
        self.assertEqual(
            TEST_BRANCH_NAME,
            entity.device_state_attributes[local_git.ATTR_BRANCH_NAME]
        )
        self.assertEqual(
            TEST_COMMIT_TITLE,
            entity.device_state_attributes[local_git.ATTR_COMMIT_TITLE]
        )
        self.assertEqual(
            local_git.STATUS_CLEAN,
            entity.device_state_attributes[local_git.ATTR_STATUS]
        )

    def test_bare_gitrepo_values(self):
        """Test bare GitRepo values."""
        entity = self._createTestEntity(
            is_bare=True,
            is_valid=True,
            is_dirty=False
        )

        self.assertEqual(STATE_UNKNOWN, entity.state)

        entity.update()

        self.assertEqual(
            "{}".format(
                TEST_CONFIG['version_control'][local_git.CONF_NAME]
            ),
            entity.name
        )
        self.assertEqual(local_git.STATE_PROBLEM, entity.state)
        self.assertNotIn(
            local_git.ATTR_BRANCH_NAME,
            entity.device_state_attributes
        )
        self.assertNotIn(
            local_git.ATTR_COMMIT_TITLE,
            entity.device_state_attributes
        )
        self.assertEqual(
            local_git.STATUS_BARE,
            entity.device_state_attributes[local_git.ATTR_STATUS]
        )

    def test_gitrepo_values_with_invalid_branch(self):
        """Test GitRepo values with invalid branch."""
        entity = self._createTestEntity(
            is_bare=False,
            is_valid=False,
            is_dirty=False
        )

        self.assertEqual(STATE_UNKNOWN, entity.state)
        entity.update()

        self.assertEqual(
            "{}".format(
                TEST_CONFIG['version_control'][local_git.CONF_NAME]
            ),
            entity.name
        )
        self.assertEqual(local_git.STATE_PROBLEM, entity.state)
        self.assertEqual(
            TEST_BRANCH_NAME,
            entity.device_state_attributes[local_git.ATTR_BRANCH_NAME]
        )
        self.assertNotIn(
            local_git.ATTR_COMMIT_TITLE,
            entity.device_state_attributes
        )
        self.assertEqual(
            local_git.STATUS_INVALID,
            entity.device_state_attributes[local_git.ATTR_STATUS]
        )

    def test_dirty_gitrepo_values(self):
        """Test dirty GitRepo values."""
        entity = self._createTestEntity(
            is_bare=False,
            is_valid=True,
            is_dirty=True
        )
        self.assertEqual(STATE_UNKNOWN, entity.state)
        entity.update()

        self.assertEqual(
            "{}".format(
                TEST_CONFIG['version_control'][local_git.CONF_NAME]
            ),
            entity.name
        )
        self.assertEqual(TEST_COMMIT_HEXSHA, entity.state)
        self.assertEqual(
            TEST_BRANCH_NAME,
            entity.device_state_attributes[local_git.ATTR_BRANCH_NAME]
        )
        self.assertEqual(
            TEST_COMMIT_TITLE,
            entity.device_state_attributes[local_git.ATTR_COMMIT_TITLE]
        )
        self.assertEqual(
            local_git.STATUS_DIRTY,
            entity.device_state_attributes[local_git.ATTR_STATUS]
        )

    @staticmethod
    def _createTestEntity(is_bare: bool, is_valid: bool, is_dirty: bool):
        """Create a test GitRepo entity based on input parameters."""
        entity = local_git.GitRepo(
            TEST_CONFIG['version_control'][local_git.CONF_NAME], repo=Mock()
        )

        entity._repo.bare = is_bare
        entity._repo.is_dirty.return_value = is_dirty
        entity._repo.active_branch.name = TEST_BRANCH_NAME
        entity._repo.active_branch.is_valid.return_value = is_valid
        entity._repo.head.commit.hexsha = TEST_COMMIT_HEXSHA
        entity._repo.head.commit.summary = TEST_COMMIT_TITLE

        return entity
