"""The tests for the local_git component."""
import unittest
from unittest.mock import Mock
from unittest.mock import patch

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
TEST_PATH = 'test_repo'
TEST_REMOTE = 'test_remote'

TEST_SERVICE_DATA = {
    local_git.ATTR_ENTITY_ID: '{}.test_name'.format(local_git.DOMAIN),
    local_git.ATTR_REMOTE: TEST_REMOTE,
    local_git.ATTR_RESET: True
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

        assert self.hass.services.has_service(
            local_git.DOMAIN, local_git.SERVICE_LOCAL_GIT_PULL)

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

    @patch('homeassistant.components.version_control.local_git.GitRepo')
    @patch('homeassistant.components.version_control.local_git._LOGGER')
    @MockDependency('git')
    def test_setup_exception_handling(self, mock_logging, mock_gitrepo,
                                      mock_git):
        """Test platform setup exception."""
        add_devices = Mock()
        exception = local_git.VersionControlException('test')
        mock_gitrepo.side_effect = exception

        self.assertFalse(
            local_git.setup_platform(
                self.hass, TEST_CONFIG['version_control'], add_devices)
        )

        mock_logging.error.assert_called_with(exception)

    @MockDependency('git')
    def test_valid_gitrepo_values(self, mock_git):
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

    @MockDependency('git')
    def test_bare_gitrepo_values(self, mock_git):
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

    @MockDependency('git')
    def test_gitrepo_values_with_invalid_branch(self, mock_git):
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

    @MockDependency('git')
    def test_dirty_gitrepo_values(self, mock_git):
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

    @MockDependency('git')
    def test_valid_repo_git_pull_with_reset(self, mock_git):
        """Test successful setup."""
        entity = self._createTestEntity(
            is_bare=False,
            is_valid=True,
            is_dirty=False
        )

        entity.git_pull(TEST_REMOTE, reset=True)
        entity._repo.git.reset.assert_called()

    @patch('homeassistant.components.version_control.local_git._LOGGER')
    @MockDependency('git')
    def test_valid_repo_git_pull_with_nonexisting_remote(
            self, mock_logging, mock_git):
        """Test successful setup."""
        mock_git.Remote().exists.return_value = False

        entity = self._createTestEntity(
            is_bare=False,
            is_valid=True,
            is_dirty=False
        )

        self.assertFalse(entity.git_pull("fake{}".format(TEST_REMOTE)))
        mock_logging.error.assert_called()

    @MockDependency('git')
    def test_valid_repo_git_pull_without_reset(self, mock_git):
        """Test successful setup."""
        entity = self._createTestEntity(
            is_bare=False,
            is_valid=True,
            is_dirty=False
        )

        entity.git_pull(TEST_REMOTE, reset=False)
        entity._repo.git.reset.assert_not_called()

    @patch('homeassistant.components.version_control.local_git.GitRepo.git_pull')  # noqa
    @MockDependency('git')
    def test_service_git_pull(self, mock_git_repo, mock_git):
        """Test successful setup."""
        self.assertTrue(
            setup_component(self.hass, 'version_control', TEST_CONFIG)
        )

        add_devices = Mock()
        local_git.setup_platform(
            self.hass, TEST_CONFIG['version_control'], add_devices
        )

        assert self.hass.services.has_service(
            domain=local_git.DOMAIN,
            service=local_git.SERVICE_LOCAL_GIT_PULL
        )
        self.hass.services.call(
            domain=local_git.DOMAIN,
            service=local_git.SERVICE_LOCAL_GIT_PULL,
            service_data=TEST_SERVICE_DATA
        )
        self.hass.block_till_done()
        self.assertTrue(mock_git_repo.called)
        self.assertTrue(
            all(
                item in TEST_SERVICE_DATA.items()
                for item in mock_git_repo.call_args[1].items()
            )
        )

    @staticmethod
    def _createTestEntity(is_bare: bool, is_valid: bool, is_dirty: bool):
        """Create a test GitRepo entity based on input parameters."""
        entity = local_git.GitRepo(
            name=TEST_CONFIG['version_control'][local_git.CONF_NAME],
            path=TEST_PATH
        )

        entity._repo.bare = is_bare
        entity._repo.is_dirty.return_value = is_dirty
        entity._repo.active_branch.name = TEST_BRANCH_NAME
        entity._repo.active_branch.is_valid.return_value = is_valid
        entity._repo.head.commit.hexsha = TEST_COMMIT_HEXSHA
        entity._repo.head.commit.summary = TEST_COMMIT_TITLE

        return entity
