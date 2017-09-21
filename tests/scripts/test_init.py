"""Test script init."""
import unittest
from unittest.mock import patch

import homeassistant.scripts as scripts


class TestScripts(unittest.TestCase):
    """Tests homeassistant.scripts module."""

    @patch('homeassistant.scripts.get_default_config_dir',
           return_value='/default')
    def test_config_per_platform(self, mock_def):
        """Test config per platform method."""
        self.assertEqual(scripts.get_default_config_dir(), '/default')
        self.assertEqual(scripts.extract_config_dir(), '/default')
        self.assertEqual(scripts.extract_config_dir(['']), '/default')
        self.assertEqual(scripts.extract_config_dir(['-c', '/arg']), '/arg')
        self.assertEqual(scripts.extract_config_dir(['--config', '/a']), '/a')
