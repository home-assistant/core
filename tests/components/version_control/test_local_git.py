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
        self.assertTrue(
            isinstance(
                add_devices.call_args[0][0][1],
                local_git.GitRepoActiveBranch)
        )
        self.assertTrue(
            isinstance(
                add_devices.call_args[0][0][2],
                local_git.GitRepoActiveCommit)
        )
        self.assertEqual(3, len(self.hass.states.all()))

    def test_setup_invalid_path(self):
        """Test setup with invalid path."""
        add_entities = Mock()

        with self.assertRaises(Exception):
            local_git.setup_platform(self.hass, self.config, add_entities)

    def test_gitrepo_with_values(self):
        """Test GitRepo with values."""
        entity = local_git.GitRepo(
            TEST_CONFIG['version_control'][local_git.CONF_NAME], repo=Mock()
        )
        entity.update()

        self.assertEqual(
            "{}".format(
                TEST_CONFIG['version_control'][local_git.CONF_NAME]
            ),
            entity.name
        )

    def test_gitrepo_activebranch_with_values(self):
        """Test GitRepoActiveBranch with values."""
        branch_name = 'master'
        entity = local_git.GitRepoActiveBranch(
            TEST_CONFIG['version_control'][local_git.CONF_NAME], repo=Mock()
        )
        entity._repo.active_branch.name = branch_name

        self.assertEqual(
            "{} Active Branch".format(
                TEST_CONFIG['version_control'][local_git.CONF_NAME]
            ),
            entity.name
        )
        self.assertEqual(STATE_UNKNOWN, entity.state)

        entity.update()

        self.assertEqual(branch_name, entity.state)

    def test_gitrepo_activecommit_values_with_valid_branch(self):
        """Test GitRepoActiveCommit values with valid branch."""
        commit_hexsha = 'test_hexsha'
        commit_summary = 'test_summary'

        entity = local_git.GitRepoActiveCommit(
            TEST_CONFIG['version_control'][local_git.CONF_NAME], repo=Mock()
        )
        entity._repo.active_branch.is_valid.return_value = True
        entity._repo.head.commit.hexsha = commit_hexsha
        entity._repo.head.commit.summary = commit_summary

        self.assertEqual(
            "{} Active Commit".format(
                TEST_CONFIG['version_control'][local_git.CONF_NAME]
            ),
            entity.name
        )
        self.assertEqual(STATE_UNKNOWN, entity.state)
        self.assertEqual(
            None,
            entity.device_state_attributes[
                local_git.ATTR_ACTIVE_COMMIT_SUMMARY
            ]
        )

        entity.update()

        self.assertEqual(commit_hexsha, entity.state)
        self.assertEqual(
            commit_summary,
            entity.device_state_attributes[
                local_git.ATTR_ACTIVE_COMMIT_SUMMARY
            ]
        )

    def test_gitrepo_activebranch_values_with_invalid_branch(self):
        """Test GitRepoActiveCommit values with invalid branch."""
        entity = local_git.GitRepoActiveCommit(
            TEST_CONFIG['version_control'][local_git.CONF_NAME], repo=Mock())
        entity._repo.active_branch.is_valid.return_value = False

        self.assertEqual(
            "{} Active Commit".format(
                TEST_CONFIG['version_control'][local_git.CONF_NAME]
            ),
            entity.name
        )
        self.assertEqual(STATE_UNKNOWN, entity.state)
        self.assertEqual(
            None,
            entity.device_state_attributes[
                local_git.ATTR_ACTIVE_COMMIT_SUMMARY
            ]
        )

        entity.update()

        self.assertEqual(local_git.STATE_INVALID, entity.state)
        self.assertEqual(
            None,
            entity.device_state_attributes[
                local_git.ATTR_ACTIVE_COMMIT_SUMMARY
            ]
        )
