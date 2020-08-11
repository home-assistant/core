"""The tests for Home Assistant ffmpeg."""

import os
import shutil
import tempfile
import unittest

import homeassistant.components.kira as kira
from homeassistant.setup import setup_component

from tests.async_mock import MagicMock, patch
from tests.common import get_test_home_assistant

TEST_CONFIG = {
    kira.DOMAIN: {
        "sensors": [
            {"name": "test_sensor", "host": "127.0.0.1", "port": 34293},
            {"name": "second_sensor", "port": 29847},
        ],
        "remotes": [
            {"host": "127.0.0.1", "port": 34293},
            {"name": "one_more", "host": "127.0.0.1", "port": 29847},
        ],
    }
}

KIRA_CODES = """
- name: test
  code: "K 00FF"
- invalid: not_a_real_code
"""


class TestKiraSetup(unittest.TestCase):
    """Test class for kira."""

    # pylint: disable=invalid-name
    def setUp(self):
        """Set up things to be run when tests are started."""
        self.hass = get_test_home_assistant()
        _base_mock = MagicMock()
        pykira = _base_mock.pykira
        pykira.__file__ = "test"
        self._module_patcher = patch.dict("sys.modules", {"pykira": pykira})
        self._module_patcher.start()

        self.work_dir = tempfile.mkdtemp()
        self.addCleanup(self.tear_down_cleanup)

    def tear_down_cleanup(self):
        """Stop everything that was started."""
        self.hass.stop()
        self._module_patcher.stop()
        shutil.rmtree(self.work_dir, ignore_errors=True)

    def test_kira_empty_config(self):
        """Kira component should load a default sensor."""
        setup_component(self.hass, kira.DOMAIN, {})
        assert len(self.hass.data[kira.DOMAIN]["sensor"]) == 1

    def test_kira_setup(self):
        """Ensure platforms are loaded correctly."""
        setup_component(self.hass, kira.DOMAIN, TEST_CONFIG)
        assert len(self.hass.data[kira.DOMAIN]["sensor"]) == 2
        assert sorted(self.hass.data[kira.DOMAIN]["sensor"].keys()) == [
            "kira",
            "kira_1",
        ]
        assert len(self.hass.data[kira.DOMAIN]["remote"]) == 2
        assert sorted(self.hass.data[kira.DOMAIN]["remote"].keys()) == [
            "kira",
            "kira_1",
        ]

    def test_kira_creates_codes(self):
        """Kira module should create codes file if missing."""
        code_path = os.path.join(self.work_dir, "codes.yaml")
        kira.load_codes(code_path)
        assert os.path.exists(code_path), "Kira component didn't create codes file"

    def test_load_codes(self):
        """Kira should ignore invalid codes."""
        code_path = os.path.join(self.work_dir, "codes.yaml")
        with open(code_path, "w") as code_file:
            code_file.write(KIRA_CODES)
        res = kira.load_codes(code_path)
        assert len(res) == 1, "Expected exactly 1 valid Kira code"
