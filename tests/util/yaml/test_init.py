"""Test Home Assistant yaml loader."""
import importlib
import io
import os
import pathlib
from typing import Any
import unittest
from unittest.mock import patch

import pytest
import yaml as pyyaml

from homeassistant.config import YAML_CONFIG_FILE, load_yaml_config_file
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
import homeassistant.util.yaml as yaml
from homeassistant.util.yaml import loader as yaml_loader

from tests.common import get_test_config_dir, patch_yaml_files


@pytest.fixture(params=["enable_c_loader", "disable_c_loader"])
def try_both_loaders(request):
    """Disable the yaml c loader."""
    if request.param != "disable_c_loader":
        yield
        return
    try:
        cloader = pyyaml.CSafeLoader
    except ImportError:
        return
    del pyyaml.CSafeLoader
    importlib.reload(yaml_loader)
    yield
    pyyaml.CSafeLoader = cloader
    importlib.reload(yaml_loader)


@pytest.fixture(params=["enable_c_dumper", "disable_c_dumper"])
def try_both_dumpers(request):
    """Disable the yaml c dumper."""
    if request.param != "disable_c_dumper":
        yield
        return
    try:
        cdumper = pyyaml.CSafeDumper
    except ImportError:
        return
    del pyyaml.CSafeDumper
    importlib.reload(yaml_loader)
    yield
    pyyaml.CSafeDumper = cdumper
    importlib.reload(yaml_loader)


def test_simple_list(try_both_loaders) -> None:
    """Test simple list."""
    conf = "config:\n  - simple\n  - list"
    with io.StringIO(conf) as file:
        doc = yaml_loader.yaml.load(file, Loader=yaml_loader.SafeLineLoader)
    assert doc["config"] == ["simple", "list"]


def test_simple_dict(try_both_loaders) -> None:
    """Test simple dict."""
    conf = "key: value"
    with io.StringIO(conf) as file:
        doc = yaml_loader.yaml.load(file, Loader=yaml_loader.SafeLineLoader)
    assert doc["key"] == "value"


@pytest.mark.parametrize("hass_config_yaml", ["message:\n  {{ states.state }}"])
def test_unhashable_key(mock_hass_config_yaml: None) -> None:
    """Test an unhashable key."""
    with pytest.raises(HomeAssistantError):
        load_yaml_config_file(YAML_CONFIG_FILE)


@pytest.mark.parametrize("hass_config_yaml", ["a: a\nnokeyhere"])
def test_no_key(try_both_loaders, mock_hass_config_yaml: None) -> None:
    """Test item without a key."""
    with pytest.raises(HomeAssistantError):
        yaml.load_yaml(YAML_CONFIG_FILE)


def test_environment_variable(try_both_loaders) -> None:
    """Test config file with environment variable."""
    os.environ["PASSWORD"] = "secret_password"
    conf = "password: !env_var PASSWORD"
    with io.StringIO(conf) as file:
        doc = yaml_loader.yaml.load(file, Loader=yaml_loader.SafeLineLoader)
    assert doc["password"] == "secret_password"
    del os.environ["PASSWORD"]


def test_environment_variable_default(try_both_loaders) -> None:
    """Test config file with default value for environment variable."""
    conf = "password: !env_var PASSWORD secret_password"
    with io.StringIO(conf) as file:
        doc = yaml_loader.yaml.load(file, Loader=yaml_loader.SafeLineLoader)
    assert doc["password"] == "secret_password"


def test_invalid_environment_variable(try_both_loaders) -> None:
    """Test config file with no environment variable sat."""
    conf = "password: !env_var PASSWORD"
    with pytest.raises(HomeAssistantError), io.StringIO(conf) as file:
        yaml_loader.yaml.load(file, Loader=yaml_loader.SafeLineLoader)


@pytest.mark.parametrize(
    ("hass_config_yaml_files", "value"),
    [({"test.yaml": "value"}, "value"), ({"test.yaml": None}, {})],
)
def test_include_yaml(
    try_both_loaders, mock_hass_config_yaml: None, value: Any
) -> None:
    """Test include yaml."""
    conf = "key: !include test.yaml"
    with io.StringIO(conf) as file:
        doc = yaml_loader.yaml.load(file, Loader=yaml_loader.SafeLineLoader)
        assert doc["key"] == value


@patch("homeassistant.util.yaml.loader.os.walk")
@pytest.mark.parametrize(
    "hass_config_yaml_files", [{"/test/one.yaml": "one", "/test/two.yaml": "two"}]
)
def test_include_dir_list(
    mock_walk, try_both_loaders, mock_hass_config_yaml: None
) -> None:
    """Test include dir list yaml."""
    mock_walk.return_value = [["/test", [], ["two.yaml", "one.yaml"]]]

    conf = "key: !include_dir_list /test"
    with io.StringIO(conf) as file:
        doc = yaml_loader.yaml.load(file, Loader=yaml_loader.SafeLineLoader)
        assert doc["key"] == sorted(["one", "two"])


@patch("homeassistant.util.yaml.loader.os.walk")
@pytest.mark.parametrize(
    "hass_config_yaml_files",
    [
        {
            "/test/zero.yaml": "zero",
            "/test/tmp2/one.yaml": "one",
            "/test/tmp2/two.yaml": "two",
        }
    ],
)
def test_include_dir_list_recursive(
    mock_walk, try_both_loaders, mock_hass_config_yaml: None
) -> None:
    """Test include dir recursive list yaml."""
    mock_walk.return_value = [
        ["/test", ["tmp2", ".ignore", "ignore"], ["zero.yaml"]],
        ["/test/tmp2", [], ["one.yaml", "two.yaml"]],
        ["/test/ignore", [], [".ignore.yaml"]],
    ]

    conf = "key: !include_dir_list /test"
    with io.StringIO(conf) as file:
        assert ".ignore" in mock_walk.return_value[0][1], "Expecting .ignore in here"
        doc = yaml_loader.yaml.load(file, Loader=yaml_loader.SafeLineLoader)
        assert "tmp2" in mock_walk.return_value[0][1]
        assert ".ignore" not in mock_walk.return_value[0][1]
        assert sorted(doc["key"]) == sorted(["zero", "one", "two"])


@patch("homeassistant.util.yaml.loader.os.walk")
@pytest.mark.parametrize(
    "hass_config_yaml_files",
    [{"/test/first.yaml": "one", "/test/second.yaml": "two"}],
)
def test_include_dir_named(
    mock_walk, try_both_loaders, mock_hass_config_yaml: None
) -> None:
    """Test include dir named yaml."""
    mock_walk.return_value = [
        ["/test", [], ["first.yaml", "second.yaml", "secrets.yaml"]]
    ]

    conf = "key: !include_dir_named /test"
    correct = {"first": "one", "second": "two"}
    with io.StringIO(conf) as file:
        doc = yaml_loader.yaml.load(file, Loader=yaml_loader.SafeLineLoader)
        assert doc["key"] == correct


@patch("homeassistant.util.yaml.loader.os.walk")
@pytest.mark.parametrize(
    "hass_config_yaml_files",
    [
        {
            "/test/first.yaml": "one",
            "/test/tmp2/second.yaml": "two",
            "/test/tmp2/third.yaml": "three",
        }
    ],
)
def test_include_dir_named_recursive(
    mock_walk, try_both_loaders, mock_hass_config_yaml: None
) -> None:
    """Test include dir named yaml."""
    mock_walk.return_value = [
        ["/test", ["tmp2", ".ignore", "ignore"], ["first.yaml"]],
        ["/test/tmp2", [], ["second.yaml", "third.yaml"]],
        ["/test/ignore", [], [".ignore.yaml"]],
    ]

    conf = "key: !include_dir_named /test"
    correct = {"first": "one", "second": "two", "third": "three"}
    with io.StringIO(conf) as file:
        assert ".ignore" in mock_walk.return_value[0][1], "Expecting .ignore in here"
        doc = yaml_loader.yaml.load(file, Loader=yaml_loader.SafeLineLoader)
        assert "tmp2" in mock_walk.return_value[0][1]
        assert ".ignore" not in mock_walk.return_value[0][1]
        assert doc["key"] == correct


@patch("homeassistant.util.yaml.loader.os.walk")
@pytest.mark.parametrize(
    "hass_config_yaml_files",
    [{"/test/first.yaml": "- one", "/test/second.yaml": "- two\n- three"}],
)
def test_include_dir_merge_list(
    mock_walk, try_both_loaders, mock_hass_config_yaml: None
) -> None:
    """Test include dir merge list yaml."""
    mock_walk.return_value = [["/test", [], ["first.yaml", "second.yaml"]]]

    conf = "key: !include_dir_merge_list /test"
    with io.StringIO(conf) as file:
        doc = yaml_loader.yaml.load(file, Loader=yaml_loader.SafeLineLoader)
        assert sorted(doc["key"]) == sorted(["one", "two", "three"])


@patch("homeassistant.util.yaml.loader.os.walk")
@pytest.mark.parametrize(
    "hass_config_yaml_files",
    [
        {
            "/test/first.yaml": "- one",
            "/test/tmp2/second.yaml": "- two",
            "/test/tmp2/third.yaml": "- three\n- four",
        }
    ],
)
def test_include_dir_merge_list_recursive(
    mock_walk, try_both_loaders, mock_hass_config_yaml: None
) -> None:
    """Test include dir merge list yaml."""
    mock_walk.return_value = [
        ["/test", ["tmp2", ".ignore", "ignore"], ["first.yaml"]],
        ["/test/tmp2", [], ["second.yaml", "third.yaml"]],
        ["/test/ignore", [], [".ignore.yaml"]],
    ]

    conf = "key: !include_dir_merge_list /test"
    with io.StringIO(conf) as file:
        assert ".ignore" in mock_walk.return_value[0][1], "Expecting .ignore in here"
        doc = yaml_loader.yaml.load(file, Loader=yaml_loader.SafeLineLoader)
        assert "tmp2" in mock_walk.return_value[0][1]
        assert ".ignore" not in mock_walk.return_value[0][1]
        assert sorted(doc["key"]) == sorted(["one", "two", "three", "four"])


@patch("homeassistant.util.yaml.loader.os.walk")
@pytest.mark.parametrize(
    "hass_config_yaml_files",
    [
        {
            "/test/first.yaml": "key1: one",
            "/test/second.yaml": "key2: two\nkey3: three",
        }
    ],
)
def test_include_dir_merge_named(
    mock_walk, try_both_loaders, mock_hass_config_yaml: None
) -> None:
    """Test include dir merge named yaml."""
    mock_walk.return_value = [["/test", [], ["first.yaml", "second.yaml"]]]

    conf = "key: !include_dir_merge_named /test"
    with io.StringIO(conf) as file:
        doc = yaml_loader.yaml.load(file, Loader=yaml_loader.SafeLineLoader)
        assert doc["key"] == {"key1": "one", "key2": "two", "key3": "three"}


@patch("homeassistant.util.yaml.loader.os.walk")
@pytest.mark.parametrize(
    "hass_config_yaml_files",
    [
        {
            "/test/first.yaml": "key1: one",
            "/test/tmp2/second.yaml": "key2: two",
            "/test/tmp2/third.yaml": "key3: three\nkey4: four",
        }
    ],
)
def test_include_dir_merge_named_recursive(
    mock_walk, try_both_loaders, mock_hass_config_yaml: None
) -> None:
    """Test include dir merge named yaml."""
    mock_walk.return_value = [
        ["/test", ["tmp2", ".ignore", "ignore"], ["first.yaml"]],
        ["/test/tmp2", [], ["second.yaml", "third.yaml"]],
        ["/test/ignore", [], [".ignore.yaml"]],
    ]

    conf = "key: !include_dir_merge_named /test"
    with io.StringIO(conf) as file:
        assert ".ignore" in mock_walk.return_value[0][1], "Expecting .ignore in here"
        doc = yaml_loader.yaml.load(file, Loader=yaml_loader.SafeLineLoader)
        assert "tmp2" in mock_walk.return_value[0][1]
        assert ".ignore" not in mock_walk.return_value[0][1]
        assert doc["key"] == {
            "key1": "one",
            "key2": "two",
            "key3": "three",
            "key4": "four",
        }


@patch("homeassistant.util.yaml.loader.open", create=True)
def test_load_yaml_encoding_error(mock_open, try_both_loaders) -> None:
    """Test raising a UnicodeDecodeError."""
    mock_open.side_effect = UnicodeDecodeError("", b"", 1, 0, "")
    with pytest.raises(HomeAssistantError):
        yaml_loader.load_yaml("test")


def test_dump(try_both_dumpers) -> None:
    """The that the dump method returns empty None values."""
    assert yaml.dump({"a": None, "b": "b"}) == "a:\nb: b\n"


def test_dump_unicode(try_both_dumpers) -> None:
    """The that the dump method returns empty None values."""
    assert yaml.dump({"a": None, "b": "привет"}) == "a:\nb: привет\n"


FILES = {}


def load_yaml(fname, string, secrets=None):
    """Write a string to file and return the parsed yaml."""
    FILES[fname] = string
    with patch_yaml_files(FILES):
        return load_yaml_config_file(fname, secrets)


class TestSecrets(unittest.TestCase):
    """Test the secrets parameter in the yaml utility."""

    # pylint: disable=invalid-name

    def setUp(self):
        """Create & load secrets file."""
        config_dir = get_test_config_dir()
        self._yaml_path = os.path.join(config_dir, YAML_CONFIG_FILE)
        self._secret_path = os.path.join(config_dir, yaml.SECRET_YAML)
        self._sub_folder_path = os.path.join(config_dir, "subFolder")
        self._unrelated_path = os.path.join(config_dir, "unrelated")

        load_yaml(
            self._secret_path,
            (
                "http_pw: pwhttp\n"
                "comp1_un: un1\n"
                "comp1_pw: pw1\n"
                "stale_pw: not_used\n"
                "logger: debug\n"
            ),
        )
        self._yaml = load_yaml(
            self._yaml_path,
            (
                "http:\n"
                "  api_password: !secret http_pw\n"
                "component:\n"
                "  username: !secret comp1_un\n"
                "  password: !secret comp1_pw\n"
                ""
            ),
            yaml_loader.Secrets(config_dir),
        )

    def tearDown(self):
        """Clean up secrets."""
        FILES.clear()

    def test_secrets_from_yaml(self):
        """Did secrets load ok."""
        expected = {"api_password": "pwhttp"}
        assert expected == self._yaml["http"]

        expected = {"username": "un1", "password": "pw1"}
        assert expected == self._yaml["component"]

    def test_secrets_from_parent_folder(self):
        """Test loading secrets from parent folder."""
        expected = {"api_password": "pwhttp"}
        self._yaml = load_yaml(
            os.path.join(self._sub_folder_path, "sub.yaml"),
            (
                "http:\n"
                "  api_password: !secret http_pw\n"
                "component:\n"
                "  username: !secret comp1_un\n"
                "  password: !secret comp1_pw\n"
                ""
            ),
            yaml_loader.Secrets(get_test_config_dir()),
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
            (
                "http:\n"
                "  api_password: !secret http_pw\n"
                "component:\n"
                "  username: !secret comp1_un\n"
                "  password: !secret comp1_pw\n"
                ""
            ),
            yaml_loader.Secrets(get_test_config_dir()),
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

    def test_secrets_logger_removed(self):
        """Ensure logger: debug was removed."""
        with pytest.raises(HomeAssistantError):
            load_yaml(self._yaml_path, "api_password: !secret logger")

    @patch("homeassistant.util.yaml.loader._LOGGER.error")
    def test_bad_logger_value(self, mock_error):
        """Ensure logger: debug was removed."""
        load_yaml(self._secret_path, "logger: info\npw: abc")
        load_yaml(
            self._yaml_path,
            "api_password: !secret pw",
            yaml_loader.Secrets(get_test_config_dir()),
        )
        assert mock_error.call_count == 1, "Expected an error about logger: value"

    def test_secrets_are_not_dict(self):
        """Did secrets handle non-dict file."""
        FILES[
            self._secret_path
        ] = "- http_pw: pwhttp\n  comp1_un: un1\n  comp1_pw: pw1\n"
        with pytest.raises(HomeAssistantError):
            load_yaml(
                self._yaml_path,
                (
                    "http:\n"
                    "  api_password: !secret http_pw\n"
                    "component:\n"
                    "  username: !secret comp1_un\n"
                    "  password: !secret comp1_pw\n"
                    ""
                ),
            )


@pytest.mark.parametrize("hass_config_yaml", ['key: [1, "2", 3]'])
def test_representing_yaml_loaded_data(
    try_both_dumpers, mock_hass_config_yaml: None
) -> None:
    """Test we can represent YAML loaded data."""
    data = load_yaml_config_file(YAML_CONFIG_FILE)
    assert yaml.dump(data) == "key:\n- 1\n- '2'\n- 3\n"


@pytest.mark.parametrize("hass_config_yaml", ["key: thing1\nkey: thing2"])
def test_duplicate_key(caplog, try_both_loaders, mock_hass_config_yaml: None) -> None:
    """Test duplicate dict keys."""
    load_yaml_config_file(YAML_CONFIG_FILE)
    assert "contains duplicate key" in caplog.text


@pytest.mark.parametrize(
    "hass_config_yaml_files",
    [{YAML_CONFIG_FILE: "key: !secret a", yaml.SECRET_YAML: "a: 1\nb: !secret a"}],
)
def test_no_recursive_secrets(
    caplog, try_both_loaders, mock_hass_config_yaml: None
) -> None:
    """Test that loading of secrets from the secrets file fails correctly."""
    with pytest.raises(HomeAssistantError) as e:
        load_yaml_config_file(YAML_CONFIG_FILE)

    assert e.value.args == ("Secrets not supported in this YAML file",)


def test_input_class() -> None:
    """Test input class."""
    input = yaml_loader.Input("hello")
    input2 = yaml_loader.Input("hello")

    assert input.name == "hello"
    assert input == input2

    assert len({input, input2}) == 1


def test_input(try_both_loaders, try_both_dumpers) -> None:
    """Test loading inputs."""
    data = {"hello": yaml.Input("test_name")}
    assert yaml.parse_yaml(yaml.dump(data)) == data


@pytest.mark.skipif(
    not os.environ.get("HASS_CI"),
    reason="This test validates that the CI has the C loader available",
)
def test_c_loader_is_available_in_ci() -> None:
    """Verify we are testing the C loader in the CI."""
    assert yaml.loader.HAS_C_LOADER is True


async def test_loading_actual_file_with_syntax(
    hass: HomeAssistant, try_both_loaders
) -> None:
    """Test loading a real file with syntax errors."""
    with pytest.raises(HomeAssistantError):
        fixture_path = pathlib.Path(__file__).parent.joinpath(
            "fixtures", "bad.yaml.txt"
        )
        await hass.async_add_executor_job(load_yaml_config_file, fixture_path)
