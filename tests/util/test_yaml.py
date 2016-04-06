"""Test Home Assistant yaml loader."""
import io
import unittest

from homeassistant.util import yaml


class TestYaml(unittest.TestCase):
    """Test util.yaml loader."""

    def test_simple_list(self):
        """Test simple list."""
        conf = "config:\n  - simple\n  - list"
        with io.StringIO(conf) as f:
            doc = yaml.yaml.safe_load(f)
        assert doc['config'] == ["simple", "list"]

    def test_simple_dict(self):
        """Test simple dict."""
        conf = "key: value"
        with io.StringIO(conf) as f:
            doc = yaml.yaml.safe_load(f)
        assert doc['key'] == 'value'

    def test_duplicate_key(self):
        """Test simple dict."""
        conf = "key: thing1\nkey: thing2"
        try:
            with io.StringIO(conf) as f:
                yaml.yaml.safe_load(f)
        except Exception:
            pass
        else:
            assert 0
