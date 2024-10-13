"""Test Home Assistant yaml loader."""

from collections.abc import Generator
import importlib
import io
import os
import pathlib
from typing import Any
import unittest
from unittest.mock import Mock, patch

import pytest
import voluptuous as vol
import yaml as pyyaml

from homeassistant.config import YAML_CONFIG_FILE, load_yaml_config_file
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.util import yaml
from homeassistant.util.yaml import loader as yaml_loader

from tests.common import extract_stack_to_frame, get_test_config_dir, patch_yaml_files


@pytest.fixture(params=["enable_c_loader", "disable_c_loader"])
def try_both_loaders(request: pytest.FixtureRequest) -> Generator[None]:
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
def try_both_dumpers(request: pytest.FixtureRequest) -> Generator[None]:
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


@pytest.mark.usefixtures("try_both_loaders")
def test_simple_list() -> None:
    """Test simple list."""
    conf = "config:\n  - simple\n  - list"
    with io.StringIO(conf) as file:
        doc = yaml_loader.parse_yaml(file)
    assert doc["config"] == ["simple", "list"]


@pytest.mark.usefixtures("try_both_loaders")
def test_simple_dict() -> None:
    """Test simple dict."""
    conf = "key: value"
    with io.StringIO(conf) as file:
        doc = yaml_loader.parse_yaml(file)
    assert doc["key"] == "value"


@pytest.mark.parametrize("hass_config_yaml", ["message:\n  {{ states.state }}"])
@pytest.mark.usefixtures("try_both_loaders", "mock_hass_config_yaml")
def test_unhashable_key() -> None:
    """Test an unhashable key."""
    with pytest.raises(HomeAssistantError):
        load_yaml_config_file(YAML_CONFIG_FILE)


@pytest.mark.parametrize("hass_config_yaml", ["a: a\nnokeyhere"])
@pytest.mark.usefixtures("try_both_loaders", "mock_hass_config_yaml")
def test_no_key() -> None:
    """Test item without a key."""
    with pytest.raises(HomeAssistantError):
        yaml.load_yaml(YAML_CONFIG_FILE)


@pytest.mark.usefixtures("try_both_loaders")
def test_environment_variable() -> None:
    """Test config file with environment variable."""
    os.environ["PASSWORD"] = "secret_password"
    conf = "password: !env_var PASSWORD"
    with io.StringIO(conf) as file:
        doc = yaml_loader.parse_yaml(file)
    assert doc["password"] == "secret_password"
    del os.environ["PASSWORD"]


@pytest.mark.usefixtures("try_both_loaders")
def test_environment_variable_default() -> None:
    """Test config file with default value for environment variable."""
    conf = "password: !env_var PASSWORD secret_password"
    with io.StringIO(conf) as file:
        doc = yaml_loader.parse_yaml(file)
    assert doc["password"] == "secret_password"


@pytest.mark.usefixtures("try_both_loaders")
def test_invalid_environment_variable() -> None:
    """Test config file with no environment variable sat."""
    conf = "password: !env_var PASSWORD"
    with pytest.raises(HomeAssistantError), io.StringIO(conf) as file:
        yaml_loader.parse_yaml(file)


@pytest.mark.parametrize(
    ("hass_config_yaml_files", "value"),
    [
        ({"test.yaml": "value"}, "value"),
        ({"test.yaml": None}, {}),
        ({"test.yaml": "123"}, 123),
    ],
)
@pytest.mark.usefixtures("try_both_loaders", "mock_hass_config_yaml")
def test_include_yaml(value: Any) -> None:
    """Test include yaml."""
    conf = "key: !include test.yaml"
    with io.StringIO(conf) as file:
        doc = yaml_loader.parse_yaml(file)
        assert doc["key"] == value


@patch("homeassistant.util.yaml.loader.os.walk")
@pytest.mark.parametrize(
    ("hass_config_yaml_files", "value"),
    [
        ({"/test/one.yaml": "one", "/test/two.yaml": "two"}, ["one", "two"]),
        ({"/test/one.yaml": "1", "/test/two.yaml": "2"}, [1, 2]),
        ({"/test/one.yaml": "1", "/test/two.yaml": None}, [1]),
    ],
)
@pytest.mark.usefixtures("try_both_loaders", "mock_hass_config_yaml")
def test_include_dir_list(mock_walk: Mock, value: Any) -> None:
    """Test include dir list yaml."""
    mock_walk.return_value = [["/test", [], ["two.yaml", "one.yaml"]]]

    conf = "key: !include_dir_list /test"
    with io.StringIO(conf) as file:
        doc = yaml_loader.parse_yaml(file)
        assert sorted(doc["key"]) == sorted(value)


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
@pytest.mark.usefixtures("try_both_loaders", "mock_hass_config_yaml")
def test_include_dir_list_recursive(mock_walk: Mock) -> None:
    """Test include dir recursive list yaml."""
    mock_walk.return_value = [
        ["/test", ["tmp2", ".ignore", "ignore"], ["zero.yaml"]],
        ["/test/tmp2", [], ["one.yaml", "two.yaml"]],
        ["/test/ignore", [], [".ignore.yaml"]],
    ]

    conf = "key: !include_dir_list /test"
    with io.StringIO(conf) as file:
        assert ".ignore" in mock_walk.return_value[0][1], "Expecting .ignore in here"
        doc = yaml_loader.parse_yaml(file)
        assert "tmp2" in mock_walk.return_value[0][1]
        assert ".ignore" not in mock_walk.return_value[0][1]
        assert sorted(doc["key"]) == sorted(["zero", "one", "two"])


@patch("homeassistant.util.yaml.loader.os.walk")
@pytest.mark.parametrize(
    ("hass_config_yaml_files", "value"),
    [
        (
            {"/test/first.yaml": "one", "/test/second.yaml": "two"},
            {"first": "one", "second": "two"},
        ),
        (
            {"/test/first.yaml": "1", "/test/second.yaml": "2"},
            {"first": 1, "second": 2},
        ),
        (
            {"/test/first.yaml": "1", "/test/second.yaml": None},
            {"first": 1, "second": {}},
        ),
    ],
)
@pytest.mark.usefixtures("try_both_loaders", "mock_hass_config_yaml")
def test_include_dir_named(mock_walk: Mock, value: Any) -> None:
    """Test include dir named yaml."""
    mock_walk.return_value = [
        ["/test", [], ["first.yaml", "second.yaml", "secrets.yaml"]]
    ]

    conf = "key: !include_dir_named /test"
    with io.StringIO(conf) as file:
        doc = yaml_loader.parse_yaml(file)
        assert doc["key"] == value


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
@pytest.mark.usefixtures("try_both_loaders", "mock_hass_config_yaml")
def test_include_dir_named_recursive(mock_walk: Mock) -> None:
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
        doc = yaml_loader.parse_yaml(file)
        assert "tmp2" in mock_walk.return_value[0][1]
        assert ".ignore" not in mock_walk.return_value[0][1]
        assert doc["key"] == correct


@patch("homeassistant.util.yaml.loader.os.walk")
@pytest.mark.parametrize(
    ("hass_config_yaml_files", "value"),
    [
        (
            {"/test/first.yaml": "- one", "/test/second.yaml": "- two\n- three"},
            ["one", "two", "three"],
        ),
        (
            {"/test/first.yaml": "- 1", "/test/second.yaml": "- 2\n- 3"},
            [1, 2, 3],
        ),
        (
            {"/test/first.yaml": "- 1", "/test/second.yaml": None},
            [1],
        ),
    ],
)
@pytest.mark.usefixtures("try_both_loaders", "mock_hass_config_yaml")
def test_include_dir_merge_list(mock_walk: Mock, value: Any) -> None:
    """Test include dir merge list yaml."""
    mock_walk.return_value = [["/test", [], ["first.yaml", "second.yaml"]]]

    conf = "key: !include_dir_merge_list /test"
    with io.StringIO(conf) as file:
        doc = yaml_loader.parse_yaml(file)
        assert sorted(doc["key"]) == sorted(value)


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
@pytest.mark.usefixtures("try_both_loaders", "mock_hass_config_yaml")
def test_include_dir_merge_list_recursive(mock_walk: Mock) -> None:
    """Test include dir merge list yaml."""
    mock_walk.return_value = [
        ["/test", ["tmp2", ".ignore", "ignore"], ["first.yaml"]],
        ["/test/tmp2", [], ["second.yaml", "third.yaml"]],
        ["/test/ignore", [], [".ignore.yaml"]],
    ]

    conf = "key: !include_dir_merge_list /test"
    with io.StringIO(conf) as file:
        assert ".ignore" in mock_walk.return_value[0][1], "Expecting .ignore in here"
        doc = yaml_loader.parse_yaml(file)
        assert "tmp2" in mock_walk.return_value[0][1]
        assert ".ignore" not in mock_walk.return_value[0][1]
        assert sorted(doc["key"]) == sorted(["one", "two", "three", "four"])


@patch("homeassistant.util.yaml.loader.os.walk")
@pytest.mark.parametrize(
    ("hass_config_yaml_files", "value"),
    [
        (
            {
                "/test/first.yaml": "key1: one",
                "/test/second.yaml": "key2: two\nkey3: three",
            },
            {"key1": "one", "key2": "two", "key3": "three"},
        ),
        (
            {
                "/test/first.yaml": "key1: 1",
                "/test/second.yaml": "key2: 2\nkey3: 3",
            },
            {"key1": 1, "key2": 2, "key3": 3},
        ),
        (
            {
                "/test/first.yaml": "key1: 1",
                "/test/second.yaml": None,
            },
            {"key1": 1},
        ),
    ],
)
@pytest.mark.usefixtures("try_both_loaders", "mock_hass_config_yaml")
def test_include_dir_merge_named(mock_walk: Mock, value: Any) -> None:
    """Test include dir merge named yaml."""
    mock_walk.return_value = [["/test", [], ["first.yaml", "second.yaml"]]]

    conf = "key: !include_dir_merge_named /test"
    with io.StringIO(conf) as file:
        doc = yaml_loader.parse_yaml(file)
        assert doc["key"] == value


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
@pytest.mark.usefixtures("try_both_loaders", "mock_hass_config_yaml")
def test_include_dir_merge_named_recursive(mock_walk: Mock) -> None:
    """Test include dir merge named yaml."""
    mock_walk.return_value = [
        ["/test", ["tmp2", ".ignore", "ignore"], ["first.yaml"]],
        ["/test/tmp2", [], ["second.yaml", "third.yaml"]],
        ["/test/ignore", [], [".ignore.yaml"]],
    ]

    conf = "key: !include_dir_merge_named /test"
    with io.StringIO(conf) as file:
        assert ".ignore" in mock_walk.return_value[0][1], "Expecting .ignore in here"
        doc = yaml_loader.parse_yaml(file)
        assert "tmp2" in mock_walk.return_value[0][1]
        assert ".ignore" not in mock_walk.return_value[0][1]
        assert doc["key"] == {
            "key1": "one",
            "key2": "two",
            "key3": "three",
            "key4": "four",
        }


@patch("homeassistant.util.yaml.loader.open", create=True)
@pytest.mark.usefixtures("try_both_loaders")
def test_load_yaml_encoding_error(mock_open: Mock) -> None:
    """Test raising a UnicodeDecodeError."""
    mock_open.side_effect = UnicodeDecodeError("", b"", 1, 0, "")
    with pytest.raises(HomeAssistantError):
        yaml_loader.load_yaml("test")


@pytest.mark.usefixtures("try_both_dumpers")
def test_dump() -> None:
    """The that the dump method returns empty None values."""
    assert yaml.dump({"a": None, "b": "b"}) == "a:\nb: b\n"


@pytest.mark.usefixtures("try_both_dumpers")
def test_dump_unicode() -> None:
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
        FILES[self._secret_path] = (
            "- http_pw: pwhttp\n  comp1_un: un1\n  comp1_pw: pw1\n"
        )
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
@pytest.mark.usefixtures("try_both_dumpers", "mock_hass_config_yaml")
def test_representing_yaml_loaded_data() -> None:
    """Test we can represent YAML loaded data."""
    data = load_yaml_config_file(YAML_CONFIG_FILE)
    assert yaml.dump(data) == "key:\n- 1\n- '2'\n- 3\n"


@pytest.mark.parametrize("hass_config_yaml", ["key: thing1\nkey: thing2"])
@pytest.mark.usefixtures("try_both_loaders", "mock_hass_config_yaml")
def test_duplicate_key(caplog: pytest.LogCaptureFixture) -> None:
    """Test duplicate dict keys."""
    load_yaml_config_file(YAML_CONFIG_FILE)
    assert "contains duplicate key" in caplog.text


@pytest.mark.parametrize(
    "hass_config_yaml_files",
    [{YAML_CONFIG_FILE: "key: !secret a", yaml.SECRET_YAML: "a: 1\nb: !secret a"}],
)
@pytest.mark.usefixtures("try_both_loaders", "mock_hass_config_yaml")
def test_no_recursive_secrets() -> None:
    """Test that loading of secrets from the secrets file fails correctly."""
    with pytest.raises(HomeAssistantError) as e:
        load_yaml_config_file(YAML_CONFIG_FILE)

    assert e.value.args == ("Secrets not supported in this YAML file",)


def test_input_class() -> None:
    """Test input class."""
    yaml_input = yaml.Input("hello")
    yaml_input2 = yaml.Input("hello")

    assert yaml_input.name == "hello"
    assert yaml_input == yaml_input2

    assert len({yaml_input, yaml_input2}) == 1


@pytest.mark.usefixtures("try_both_loaders", "try_both_dumpers")
def test_input() -> None:
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


@pytest.mark.usefixtures("try_both_loaders")
async def test_loading_actual_file_with_syntax_error(hass: HomeAssistant) -> None:
    """Test loading a real file with syntax errors."""
    fixture_path = pathlib.Path(__file__).parent.joinpath("fixtures", "bad.yaml.txt")
    with pytest.raises(HomeAssistantError):
        await hass.async_add_executor_job(load_yaml_config_file, fixture_path)


@pytest.fixture
def mock_integration_frame() -> Generator[Mock]:
    """Mock as if we're calling code from inside an integration."""
    correct_frame = Mock(
        filename="/home/paulus/homeassistant/components/hue/light.py",
        lineno="23",
        line="self.light.is_on",
    )
    with (
        patch(
            "homeassistant.helpers.frame.linecache.getline",
            return_value=correct_frame.line,
        ),
        patch(
            "homeassistant.helpers.frame.get_current_frame",
            return_value=extract_stack_to_frame(
                [
                    Mock(
                        filename="/home/paulus/homeassistant/core.py",
                        lineno="23",
                        line="do_something()",
                    ),
                    correct_frame,
                    Mock(
                        filename="/home/paulus/aiohue/lights.py",
                        lineno="2",
                        line="something()",
                    ),
                ]
            ),
        ),
    ):
        yield correct_frame


@pytest.mark.parametrize(
    ("loader_class", "message"),
    [
        (yaml.loader.SafeLoader, "'SafeLoader' instead of 'FastSafeLoader'"),
        (
            yaml.loader.SafeLineLoader,
            "'SafeLineLoader' instead of 'PythonSafeLoader'",
        ),
    ],
)
@pytest.mark.usefixtures("mock_integration_frame")
async def test_deprecated_loaders(
    caplog: pytest.LogCaptureFixture,
    loader_class: type,
    message: str,
) -> None:
    """Test instantiating the deprecated yaml loaders logs a warning."""
    with (
        pytest.raises(TypeError),
        patch("homeassistant.helpers.frame._REPORTED_INTEGRATIONS", set()),
    ):
        loader_class()
    assert (f"Detected that integration 'hue' uses deprecated {message}") in caplog.text


@pytest.mark.usefixtures("try_both_loaders")
def test_string_annotated() -> None:
    """Test strings are annotated with file + line."""
    conf = (
        "key1: str\n"
        "key2:\n"
        "  blah: blah\n"
        "key3:\n"
        " - 1\n"
        " - 2\n"
        " - 3\n"
        "key4: yes\n"
        "key5: 1\n"
        "key6: 1.0\n"
    )
    expected_annotations = {
        "key1": [("<file>", 1), ("<file>", 1)],
        "key2": [("<file>", 2), ("<file>", 3)],
        "key3": [("<file>", 4), ("<file>", 5)],
        "key4": [("<file>", 8), (None, None)],
        "key5": [("<file>", 9), (None, None)],
        "key6": [("<file>", 10), (None, None)],
    }
    with io.StringIO(conf) as file:
        doc = yaml_loader.parse_yaml(file)
    for key, value in doc.items():
        assert getattr(key, "__config_file__", None) == expected_annotations[key][0][0]
        assert getattr(key, "__line__", None) == expected_annotations[key][0][1]
        assert (
            getattr(value, "__config_file__", None) == expected_annotations[key][1][0]
        )
        assert getattr(value, "__line__", None) == expected_annotations[key][1][1]


@pytest.mark.usefixtures("try_both_loaders")
def test_string_used_as_vol_schema() -> None:
    """Test the subclassed strings can be used in voluptuous schemas."""
    conf = "wanted_data:\n  key_1: value_1\n  key_2: value_2\n"
    with io.StringIO(conf) as file:
        doc = yaml_loader.parse_yaml(file)

    # Test using the subclassed strings in a schema
    schema = vol.Schema(
        {vol.Required(key): value for key, value in doc["wanted_data"].items()},
    )
    # Test using the subclassed strings when validating a schema
    schema(doc["wanted_data"])
    schema({"key_1": "value_1", "key_2": "value_2"})
    with pytest.raises(vol.Invalid):
        schema({"key_1": "value_2", "key_2": "value_1"})


@pytest.mark.parametrize(
    ("hass_config_yaml", "expected_data"), [("", {}), ("bla:", {"bla": None})]
)
@pytest.mark.usefixtures("try_both_loaders", "mock_hass_config_yaml")
def test_load_yaml_dict(expected_data: Any) -> None:
    """Test item without a key."""
    assert yaml.load_yaml_dict(YAML_CONFIG_FILE) == expected_data


@pytest.mark.parametrize("hass_config_yaml", ["abc", "123", "[]"])
@pytest.mark.usefixtures("try_both_loaders", "mock_hass_config_yaml")
def test_load_yaml_dict_fail() -> None:
    """Test item without a key."""
    with pytest.raises(yaml_loader.YamlTypeError):
        yaml_loader.load_yaml_dict(YAML_CONFIG_FILE)


@pytest.mark.parametrize(
    "tag",
    [
        "!include",
        "!include_dir_named",
        "!include_dir_merge_named",
        "!include_dir_list",
        "!include_dir_merge_list",
    ],
)
@pytest.mark.usefixtures("try_both_loaders")
def test_include_without_parameter(tag: str) -> None:
    """Test include extensions without parameters."""
    with (
        io.StringIO(f"key: {tag}") as file,
        pytest.raises(HomeAssistantError, match=f"{tag} needs an argument"),
    ):
        yaml_loader.parse_yaml(file)


@pytest.mark.parametrize(
    ("open_exception", "load_yaml_exception"),
    [
        (FileNotFoundError, OSError),
        (NotADirectoryError, HomeAssistantError),
        (PermissionError, HomeAssistantError),
    ],
)
@pytest.mark.usefixtures("try_both_loaders")
def test_load_yaml_wrap_oserror(
    open_exception: Exception,
    load_yaml_exception: Exception,
) -> None:
    """Test load_yaml wraps OSError in HomeAssistantError."""
    with (
        patch("homeassistant.util.yaml.loader.open", side_effect=open_exception),
        pytest.raises(load_yaml_exception),
    ):
        yaml_loader.load_yaml("bla")
