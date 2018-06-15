"""The tests for the GitLab component."""
import unittest
from unittest.mock import Mock
from unittest.mock import patch

from homeassistant.const import (STATE_UNKNOWN)

from homeassistant.components.version_control import gitlab as gitlab
from homeassistant.setup import setup_component
from tests.common import (get_test_home_assistant, MockDependency)

TEST_CONFIG = {
    'version_control': {
        'platform': 'gitlab',
        gitlab.CONF_NAME: 'test_name',
        gitlab.CONF_TOKEN: 'test_path',
        gitlab.CONF_PROJECT: 'test_token'
    }
}

TEST_BRANCH_NAME = 'master'
TEST_COMMIT_HEXSHA = 'test_hexsha'
TEST_COMMIT_TITLE = 'test_title'
TEST_PIPELINE_STATUS = 'success'
TEST_PROJECT_NAME = 'test/project'


class TestGitlab(unittest.TestCase):
    """Test the GitLab platform."""

    def setUp(self):
        """Initialize values for this test case class."""
        self.hass = get_test_home_assistant()
        self.config = TEST_CONFIG

    @patch('homeassistant.components.version_control.gitlab.GitLabData')
    @patch('homeassistant.components.version_control.gitlab._LOGGER')
    @MockDependency('gitlab')
    def test_setup_exception_handling(
            self, mock_logging, mock_gitlab_data, mock_gitlab):
        """Test setup exception handling."""
        add_entities = Mock()
        exception = gitlab.VersionControlException('test')

        mock_gitlab_data.side_effect = exception

        self.assertFalse(
            gitlab.setup_platform(self.hass, self.config, add_entities)
        )

        mock_logging.error.assert_called_with(exception)

    def tearDown(self):  # pylint: disable=invalid-name
        """Stop everything that we started."""
        self.hass.stop()

    @MockDependency('gitlab')
    def test_setup_platform(self, mock_gitlab):
        """Test successful setup."""
        self.assertTrue(
            setup_component(self.hass, 'version_control', TEST_CONFIG)
        )

        add_devices = Mock()
        gitlab.setup_platform(
            self.hass, TEST_CONFIG['version_control'], add_devices
        )

        self.assertTrue(add_devices.called)
        self.assertTrue(
            isinstance(
                add_devices.call_args[0][0][0],
                gitlab.GitLabRepo)
        )
        self.assertEqual(1, len(self.hass.states.all()))

    def test_valid_gitlabrepo_values_with_pipeline(self):
        """Test valid GitLab repo values with pipeline."""
        entity = self._createTestEntity(
            with_pipeline=True
        )

        self.assertEqual(STATE_UNKNOWN, entity.state)

        entity.update()

        self.assertEqual(
            "{}".format(
                TEST_CONFIG['version_control'][gitlab.CONF_NAME]
            ),
            entity.name
        )
        self.assertEqual(TEST_COMMIT_HEXSHA, entity.state)
        self.assertEqual(
            TEST_PROJECT_NAME,
            entity.device_state_attributes[gitlab.ATTR_PROJECT]
        )
        self.assertEqual(
            TEST_BRANCH_NAME,
            entity.device_state_attributes[gitlab.ATTR_BRANCH_NAME]
        )
        self.assertEqual(
            TEST_COMMIT_TITLE,
            entity.device_state_attributes[gitlab.ATTR_COMMIT_TITLE]
        )
        self.assertEqual(
            TEST_PIPELINE_STATUS,
            entity.device_state_attributes[gitlab.ATTR_PIPELINE_STATUS]
        )

    def test_valid_gitlabrepo_values_without_pipeline(self):
        """Test valid GitLab repo values without pipeline."""
        entity = self._createTestEntity(
            with_pipeline=False
        )

        self.assertEqual(STATE_UNKNOWN, entity.state)

        entity.update()

        self.assertEqual(
            "{}".format(
                TEST_CONFIG['version_control'][gitlab.CONF_NAME]
            ),
            entity.name
        )
        self.assertEqual(TEST_COMMIT_HEXSHA, entity.state)
        self.assertEqual(
            TEST_PROJECT_NAME,
            entity.device_state_attributes[gitlab.ATTR_PROJECT]
        )
        self.assertEqual(
            TEST_BRANCH_NAME,
            entity.device_state_attributes[gitlab.ATTR_BRANCH_NAME]
        )
        self.assertEqual(
            TEST_COMMIT_TITLE,
            entity.device_state_attributes[gitlab.ATTR_COMMIT_TITLE]
        )
        self.assertNotIn(
            gitlab.ATTR_PIPELINE_STATUS,
            entity.device_state_attributes
        )

    @staticmethod
    def _createTestEntity(with_pipeline: bool):
        """Create a test GitLabRepo entity based on input parameters."""
        entity = gitlab.GitLabRepo(
            name=TEST_CONFIG['version_control'][gitlab.CONF_NAME],
            gitlab_data=Mock()
        )

        entity.gitlab_data.project.attributes = {
            'path_with_namespace': TEST_PROJECT_NAME
        }

        entity.gitlab_data.branch.name = TEST_BRANCH_NAME
        entity.gitlab_data.branch.commit = {
            'id': TEST_COMMIT_HEXSHA,
            'title': TEST_COMMIT_TITLE
        }

        if with_pipeline:
            entity.gitlab_data.pipeline.status = TEST_PIPELINE_STATUS
        else:
            entity.gitlab_data.pipeline = None

        return entity
