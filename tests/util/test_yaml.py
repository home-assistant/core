"""Test Home Assistant yaml loader."""
import io
import logging
import os
import unittest

import pytest

from homeassistant.config import YAML_CONFIG_FILE, load_yaml_config_file
from homeassistant.exceptions import HomeAssistantError
import homeassistant.util.yaml as yaml
from homeassistant.util.yaml import loader as yaml_loader

from tests.async_mock import patch
from tests.common import get_test_config_dir, patch_yaml_files


@pytest.fixture(autouse=True)
def mock_credstash():
    """Mock credstash so it doesn't connect to the internet."""
    with patch.object(yaml_loader, "credstash") as mock_credstash:
        mock_credstash.getSecret.return_value = None
        yield mock_credstash


def test_simple_list():
    """Test simple list."""
    conf = "config:\n  - simple\n  - list"
    with io.StringIO(conf) as file:
        doc = yaml_loader.yaml.safe_load(file)
    assert doc["config"] == ["simple", "list"]


def test_simple_dict():
    """Test simple dict."""
    conf = "key: value"
    with io.StringIO(conf) as file:
        doc = yaml_loader.yaml.safe_load(file)
    assert doc["key"] == "value"


def test_unhashable_key():
    """Test an unhashable key."""
    files = {YAML_CONFIG_FILE: "message:\n  {{ states.state }}"}
    with pytest.raises(HomeAssistantError), patch_yaml_files(files):
        load_yaml_config_file(YAML_CONFIG_FILE)


def test_no_key():
    """Test item without a key."""
    files = {YAML_CONFIG_FILE: "a: a\nnokeyhere"}
    with pytest.raises(HomeAssistantError), patch_yaml_files(files):
        yaml.load_yaml(YAML_CONFIG_FILE)


def test_environment_variable():
    """Test config file with environment variable."""
    os.environ["PASSWORD"] = "secret_password"
    conf = "password: !env_var PASSWORD"
    with io.StringIO(conf) as file:
        doc = yaml_loader.yaml.safe_load(file)
    assert doc["password"] == "secret_password"
    del os.environ["PASSWORD"]


def test_environment_variable_default():
    """Test config file with default value for environment variable."""
    conf = "password: !env_var PASSWORD secret_password"
    with io.StringIO(conf) as file:
        doc = yaml_loader.yaml.safe_load(file)
    assert doc["password"] == "secret_password"


def test_invalid_environment_variable():
    """Test config file with no environment variable sat."""
    conf = "password: !env_var PASSWORD"
    with pytest.raises(HomeAssistantError):
        with io.StringIO(conf) as file:
            yaml_loader.yaml.safe_load(file)


def test_include_yaml():
    """Test include yaml."""
    with patch_yaml_files({"test.yaml": "value"}):
        conf = "key: !include test.yaml"
        with io.StringIO(conf) as file:
            doc = yaml_loader.yaml.safe_load(file)
            assert doc["key"] == "value"

    with patch_yaml_files({"test.yaml": None}):
        conf = "key: !include test.yaml"
        with io.StringIO(conf) as file:
            doc = yaml_loader.yaml.safe_load(file)
            assert doc["key"] == {}


@patch("homeassistant.util.yaml.loader.os.walk")
def test_include_dir_list(mock_walk):
    """Test include dir list yaml."""
    mock_walk.return_value = [["/test", [], ["two.yaml", "one.yaml"]]]

    with patch_yaml_files({"/test/one.yaml": "one", "/test/two.yaml": "two"}):
        conf = "key: !include_dir_list /test"
        with io.StringIO(conf) as file:
            doc = yaml_loader.yaml.safe_load(file)
            assert doc["key"] == sorted(["one", "two"])


@patch("homeassistant.util.yaml.loader.os.walk")
def test_include_dir_list_recursive(mock_walk):
    """Test include dir recursive list yaml."""
    mock_walk.return_value = [
        ["/test", ["tmp2", ".ignore", "ignore"], ["zero.yaml"]],
        ["/test/tmp2", [], ["one.yaml", "two.yaml"]],
        ["/test/ignore", [], [".ignore.yaml"]],
    ]

    with patch_yaml_files(
        {
            "/test/zero.yaml": "zero",
            "/test/tmp2/one.yaml": "one",
            "/test/tmp2/two.yaml": "two",
        }
    ):
        conf = "key: !include_dir_list /test"
        with io.StringIO(conf) as file:
            assert (
                ".ignore" in mock_walk.return_value[0][1]
            ), "Expecting .ignore in here"
            doc = yaml_loader.yaml.safe_load(file)
            assert "tmp2" in mock_walk.return_value[0][1]
            assert ".ignore" not in mock_walk.return_value[0][1]
            assert sorted(doc["key"]) == sorted(["zero", "one", "two"])


@patch("homeassistant.util.yaml.loader.os.walk")
def test_include_dir_named(mock_walk):
    """Test include dir named yaml."""
    mock_walk.return_value = [
        ["/test", [], ["first.yaml", "second.yaml", "secrets.yaml"]]
    ]

    with patch_yaml_files({"/test/first.yaml": "one", "/test/second.yaml": "two"}):
        conf = "key: !include_dir_named /test"
        correct = {"first": "one", "second": "two"}
        with io.StringIO(conf) as file:
            doc = yaml_loader.yaml.safe_load(file)
            assert doc["key"] == correct


@patch("homeassistant.util.yaml.loader.os.walk")
def test_include_dir_named_recursive(mock_walk):
    """Test include dir named yaml."""
    mock_walk.return_value = [
        ["/test", ["tmp2", ".ignore", "ignore"], ["first.yaml"]],
        ["/test/tmp2", [], ["second.yaml", "third.yaml"]],
        ["/test/ignore", [], [".ignore.yaml"]],
    ]

    with patch_yaml_files(
        {
            "/test/first.yaml": "one",
            "/test/tmp2/second.yaml": "two",
            "/test/tmp2/third.yaml": "three",
        }
    ):
        conf = "key: !include_dir_named /test"
        correct = {"first": "one", "second": "two", "third": "three"}
        with io.StringIO(conf) as file:
            assert (
                ".ignore" in mock_walk.return_value[0][1]
            ), "Expecting .ignore in here"
            doc = yaml_loader.yaml.safe_load(file)
            assert "tmp2" in mock_walk.return_value[0][1]
            assert ".ignore" not in mock_walk.return_value[0][1]
            assert doc["key"] == correct


@patch("homeassistant.util.yaml.loader.os.walk")
def test_include_dir_merge_list(mock_walk):
    """Test include dir merge list yaml."""
    mock_walk.return_value = [["/test", [], ["first.yaml", "second.yaml"]]]

    with patch_yaml_files(
        {"/test/first.yaml": "- one", "/test/second.yaml": "- two\n- three"}
    ):
        conf = "key: !include_dir_merge_list /test"
        with io.StringIO(conf) as file:
            doc = yaml_loader.yaml.safe_load(file)
            assert sorted(doc["key"]) == sorted(["one", "two", "three"])


@patch("homeassistant.util.yaml.loader.os.walk")
def test_include_dir_merge_list_recursive(mock_walk):
    """Test include dir merge list yaml."""
    mock_walk.return_value = [
        ["/test", ["tmp2", ".ignore", "ignore"], ["first.yaml"]],
        ["/test/tmp2", [], ["second.yaml", "third.yaml"]],
        ["/test/ignore", [], [".ignore.yaml"]],
    ]

    with patch_yaml_files(
        {
            "/test/first.yaml": "- one",
            "/test/tmp2/second.yaml": "- two",
            "/test/tmp2/third.yaml": "- three\n- four",
        }
    ):
        conf = "key: !include_dir_merge_list /test"
        with io.StringIO(conf) as file:
            assert (
                ".ignore" in mock_walk.return_value[0][1]
            ), "Expecting .ignore in here"
            doc = yaml_loader.yaml.safe_load(file)
            assert "tmp2" in mock_walk.return_value[0][1]
            assert ".ignore" not in mock_walk.return_value[0][1]
            assert sorted(doc["key"]) == sorted(["one", "two", "three", "four"])


@patch("homeassistant.util.yaml.loader.os.walk")
def test_include_dir_merge_named(mock_walk):
    """Test include dir merge named yaml."""
    mock_walk.return_value = [["/test", [], ["first.yaml", "second.yaml"]]]

    files = {
        "/test/first.yaml": "key1: one",
        "/test/second.yaml": "key2: two\nkey3: three",
    }

    with patch_yaml_files(files):
        conf = "key: !include_dir_merge_named /test"
        with io.StringIO(conf) as file:
            doc = yaml_loader.yaml.safe_load(file)
            assert doc["key"] == {"key1": "one", "key2": "two", "key3": "three"}


@patch("homeassistant.util.yaml.loader.os.walk")
def test_include_dir_merge_named_recursive(mock_walk):
    """Test include dir merge named yaml."""
    mock_walk.return_value = [
        ["/test", ["tmp2", ".ignore", "ignore"], ["first.yaml"]],
        ["/test/tmp2", [], ["second.yaml", "third.yaml"]],
        ["/test/ignore", [], [".ignore.yaml"]],
    ]

    with patch_yaml_files(
        {
            "/test/first.yaml": "key1: one",
            "/test/tmp2/second.yaml": "key2: two",
            "/test/tmp2/third.yaml": "key3: three\nkey4: four",
        }
    ):
        conf = "key: !include_dir_merge_named /test"
        with io.StringIO(conf) as file:
            assert (
                ".ignore" in mock_walk.return_value[0][1]
            ), "Expecting .ignore in here"
            doc = yaml_loader.yaml.safe_load(file)
            assert "tmp2" in mock_walk.return_value[0][1]
            assert ".ignore" not in mock_walk.return_value[0][1]
            assert doc["key"] == {
                "key1": "one",
                "key2": "two",
                "key3": "three",
                "key4": "four",
            }


@patch("homeassistant.util.yaml.loader.open", create=True)
def test_load_yaml_encoding_error(mock_open):
    """Test raising a UnicodeDecodeError."""
    mock_open.side_effect = UnicodeDecodeError("", b"", 1, 0, "")
    with pytest.raises(HomeAssistantError):
        yaml_loader.load_yaml("test")


def test_dump():
    """The that the dump method returns empty None values."""
    assert yaml.dump({"a": None, "b": "b"}) == "a:\nb: b\n"


def test_dump_unicode():
    """The that the dump method returns empty None values."""
    assert yaml.dump({"a": None, "b": "привет"}) == "a:\nb: привет\n"


FILES = {}


def load_yaml(fname, string):
    """Write a string to file and return the parsed yaml."""
    FILES[fname] = string
    with patch_yaml_files(FILES):
        return load_yaml_config_file(fname)


class FakeKeyring:
    """Fake a keyring class."""

    def __init__(self, secrets_dict):
        """Store keyring dictionary."""
        self._secrets = secrets_dict

    # pylint: disable=protected-access
    def get_password(self, domain, name):
        """Retrieve password."""
        assert domain == yaml._SECRET_NAMESPACE
        return self._secrets.get(name)


class TestSecrets(unittest.TestCase):
    """Test the secrets parameter in the yaml utility."""

    # pylint: disable=protected-access,invalid-name

    def setUp(self):
        """Create & load secrets file."""
        config_dir = get_test_config_dir()
        yaml.clear_secret_cache()
        self._yaml_path = os.path.join(config_dir, YAML_CONFIG_FILE)
        self._secret_path = os.path.join(config_dir, yaml.SECRET_YAML)
        self._sub_folder_path = os.path.join(config_dir, "subFolder")
        self._unrelated_path = os.path.join(config_dir, "unrelated")

        load_yaml(
            self._secret_path,
            "http_pw: pwhttp\n"
            "comp1_un: un1\n"
            "comp1_pw: pw1\n"
            "stale_pw: not_used\n"
            "logger: debug\n",
        )
        self._yaml = load_yaml(
            self._yaml_path,
            "http:\n"
            "  api_password: !secret http_pw\n"
            "component:\n"
            "  username: !secret comp1_un\n"
            "  password: !secret comp1_pw\n"
            "",
        )

    def tearDown(self):
        """Clean up secrets."""
        yaml.clear_secret_cache()
        FILES.clear()

    def test_secrets_from_yaml(self):
        """Did secrets load ok."""
        expected = {"api_password": "pwhttp"}
        assert expected == self._yaml["http"]

        expected = {"username": "un1", "password": "pw1"}
        assert expected == self._yaml["component"]

    def test_secrets_from_parent_folder(self):
        """Test loading secrets from parent foler."""
        expected = {"api_password": "pwhttp"}
        self._yaml = load_yaml(
            os.path.join(self._sub_folder_path, "sub.yaml"),
            "http:\n"
            "  api_password: !secret http_pw\n"
            "component:\n"
            "  username: !secret comp1_un\n"
            "  password: !secret comp1_pw\n"
            "",
        )

        assert expected == self._yaml["http"]

    def test_secret_overrides_parent(self):
        """Test loading current directory secret overrides the parent."""
        expected = {"api_password": "override"}
        load_yaml(
            os.path.join(self._sub_folder_path, yaml.SECRET_YAML), "http_pw: override"
        )
        self._yaml = load_yaml(
            os.path.join(self._sub_folder_path, "sub.yaml"),
            "http:\n"
            "  api_password: !secret http_pw\n"
            "component:\n"
            "  username: !secret comp1_un\n"
            "  password: !secret comp1_pw\n"
            "",
        )

        assert expected == self._yaml["http"]

    def test_secrets_from_unrelated_fails(self):
        """Test loading secrets from unrelated folder fails."""
        load_yaml(os.path.join(self._unrelated_path, yaml.SECRET_YAML), "test: failure")
        with pytest.raises(HomeAssistantError):
            load_yaml(
                os.path.join(self._sub_folder_path, "sub.yaml"),
                "http:\n  api_password: !secret test",
            )

    def test_secrets_keyring(self):
        """Test keyring fallback & get_password."""
        yaml_loader.keyring = None  # Ensure its not there
        yaml_str = "http:\n  api_password: !secret http_pw_keyring"
        with pytest.raises(HomeAssistantError):
            load_yaml(self._yaml_path, yaml_str)

        yaml_loader.keyring = FakeKeyring({"http_pw_keyring": "yeah"})
        _yaml = load_yaml(self._yaml_path, yaml_str)
        assert {"http": {"api_password": "yeah"}} == _yaml

    @patch.object(yaml_loader, "credstash")
    def test_secrets_credstash(self, mock_credstash):
        """Test credstash fallback & get_password."""
        mock_credstash.getSecret.return_value = "yeah"
        yaml_str = "http:\n  api_password: !secret http_pw_credstash"
        _yaml = load_yaml(self._yaml_path, yaml_str)
        log = logging.getLogger()
        log.error(_yaml["http"])
        assert {"api_password": "yeah"} == _yaml["http"]

    def test_secrets_logger_removed(self):
        """Ensure logger: debug was removed."""
        with pytest.raises(HomeAssistantError):
            load_yaml(self._yaml_path, "api_password: !secret logger")

    @patch("homeassistant.util.yaml.loader._LOGGER.error")
    def test_bad_logger_value(self, mock_error):
        """Ensure logger: debug was removed."""
        yaml.clear_secret_cache()
        load_yaml(self._secret_path, "logger: info\npw: abc")
        load_yaml(self._yaml_path, "api_password: !secret pw")
        assert mock_error.call_count == 1, "Expected an error about logger: value"

    def test_secrets_are_not_dict(self):
        """Did secrets handle non-dict file."""
        FILES[
            self._secret_path
        ] = "- http_pw: pwhttp\n  comp1_un: un1\n  comp1_pw: pw1\n"
        yaml.clear_secret_cache()
        with pytest.raises(HomeAssistantError):
            load_yaml(
                self._yaml_path,
                "http:\n"
                "  api_password: !secret http_pw\n"
                "component:\n"
                "  username: !secret comp1_un\n"
                "  password: !secret comp1_pw\n"
                "",
            )


def test_representing_yaml_loaded_data():
    """Test we can represent YAML loaded data."""
    files = {YAML_CONFIG_FILE: 'key: [1, "2", 3]'}
    with patch_yaml_files(files):
        data = load_yaml_config_file(YAML_CONFIG_FILE)
    assert yaml.dump(data) == "key:\n- 1\n- '2'\n- 3\n"


def test_duplicate_key(caplog):
    """Test duplicate dict keys."""
    files = {YAML_CONFIG_FILE: "key: thing1\nkey: thing2"}
    with patch_yaml_files(files):
        load_yaml_config_file(YAML_CONFIG_FILE)
    assert "contains duplicate key" in caplog.text
