"""Test abstract template entity."""

from typing import Any

import pytest

from homeassistant.components.template import entity as abstract_entity
from homeassistant.components.template.template_entity import TemplateEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.template import Template

from .conftest import Brewery


def expect_boolean_on(true_value: Any = True) -> list[tuple[Any, Any]]:
    """Tuple of commonn boolean on value expected pairs."""
    return [
        ("on", true_value),
        ("On", true_value),
        ("oN", true_value),
        ("true", true_value),
        ("yes", true_value),
        ("enable", true_value),
        ("1", true_value),
        (True, true_value),
        (1, true_value),
        (8.23432, true_value),
        (0.23432, true_value),
    ]


def expect_boolean_off(false_value: Any = False) -> list[tuple[Any, Any]]:
    """Tuple of commonn boolean off value expected pairs."""
    return [
        ("off", false_value),
        ("false", false_value),
        ("no", false_value),
        ("disable", false_value),
        ("0", false_value),
        (False, false_value),
        (0, false_value),
    ]


def expect_none(*args: Any) -> list[tuple, None]:
    """Tuple of results that should return None."""
    return [(v, None) for v in args]


def check_for_error(value: Any, expected: Any, caplog_text: str, error: str) -> None:
    """Test the validator error."""
    if expected is None and value is not None:
        assert error in caplog_text
    else:
        assert error not in caplog_text


def create_result_handler(
    hass: HomeAssistant, config: dict
) -> abstract_entity.TemplateResultHandler:
    """Create a template result handler."""

    class Test(TemplateEntity):
        _entity_id_format = "test.{}"

    config = {"name": Template("Test", hass), **config}

    entity = Test(hass, config, "a")
    return abstract_entity.TemplateResultHandler(entity)


async def test_template_entity_not_implemented(hass: HomeAssistant) -> None:
    """Test abstract template entity raises not implemented error."""

    with pytest.raises(TypeError):
        _ = abstract_entity.AbstractTemplateEntity(hass, {})


@pytest.mark.parametrize(
    ("config", "error"),
    [
        (
            {"default_entity_id": "test.test"},
            "Received invalid test state: {} for entity test.test, expected: mmmm, beer, is, good",
        ),
        (
            {},
            "Received invalid state: {} for entity Test, expected: mmmm, beer, is, good",
        ),
    ],
)
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("mmmm", Brewery.MMMM),
        ("MmMM", Brewery.MMMM),
        ("mmMM", Brewery.MMMM),
        ("beer", Brewery.BEER),
        ("is", Brewery.IS),
        ("good", Brewery.GOOD),
        *expect_none(
            None,
            "mm",
            "beeal;dfj",
            "unknown",
            "unavailable",
            "tru",  # codespell:ignore tru
            "7",
            "-1",
            True,
            False,
            1,
            1.0,
            {},
            {"junk": "stuff"},
            {"junk"},
            [],
            ["stuff"],
        ),
    ],
)
async def test_enum(
    hass: HomeAssistant,
    config: dict,
    error: str,
    value: Any,
    expected: bool | None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test enum validator."""
    result_handler = create_result_handler(hass, config)
    assert result_handler.enum("state", Brewery)(value) == expected
    check_for_error(value, expected, caplog.text, error.format(value))


@pytest.mark.parametrize(
    ("config", "error"),
    [
        (
            {"default_entity_id": "test.test"},
            "Received invalid test state: {} for entity test.test, expected: mmmm, beer, is, good, 1, true, yes, on, enable, 0, false, no, off, disable",
        ),
        (
            {},
            "Received invalid state: {} for entity Test, expected: mmmm, beer, is, good, 1, true, yes, on, enable, 0, false, no, off, disable",
        ),
    ],
)
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("mmmm", Brewery.MMMM),
        ("MmMM", Brewery.MMMM),
        ("mmMM", Brewery.MMMM),
        ("beer", Brewery.BEER),
        ("is", Brewery.IS),
        ("good", Brewery.GOOD),
        *expect_boolean_on(Brewery.MMMM),
        *expect_boolean_off(Brewery.BEER),
        *expect_none(
            None,
            "mm",
            "beeal;dfj",
            "unknown",
            "unavailable",
            "tru",  # codespell:ignore tru
            "7",
            "-1",
            {},
            {"junk": "stuff"},
            {"junk"},
            [],
            ["stuff"],
        ),
    ],
)
async def test_enum_with_on_off(
    hass: HomeAssistant,
    config: dict,
    error: str,
    value: Any,
    expected: bool | None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test enum validator."""
    result_handler = create_result_handler(hass, config)
    assert (
        result_handler.enum("state", Brewery, Brewery.MMMM, Brewery.BEER)(value)
        == expected
    )
    check_for_error(value, expected, caplog.text, error.format(value))


@pytest.mark.parametrize(
    ("config", "error"),
    [
        (
            {"default_entity_id": "test.test"},
            "Received invalid test state: {} for entity test.test, expected: mmmm, beer, is, good, 1, true, yes, on, enable",
        ),
        (
            {},
            "Received invalid state: {} for entity Test, expected: mmmm, beer, is, good, 1, true, yes, on, enable",
        ),
    ],
)
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("mmmm", Brewery.MMMM),
        ("MmMM", Brewery.MMMM),
        ("mmMM", Brewery.MMMM),
        ("beer", Brewery.BEER),
        ("is", Brewery.IS),
        ("good", Brewery.GOOD),
        *expect_boolean_on(Brewery.MMMM),
        *expect_boolean_off(None),
        *expect_none(
            None,
            "mm",
            "beeal;dfj",
            "unknown",
            "unavailable",
            "tru",  # codespell:ignore tru
            "7",
            "-1",
            {},
            {"junk": "stuff"},
            {"junk"},
            [],
            ["stuff"],
        ),
    ],
)
async def test_enum_with_on(
    hass: HomeAssistant,
    config: dict,
    error: str,
    value: Any,
    expected: bool | None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test enum with state_on validator."""
    result_handler = create_result_handler(hass, config)
    assert (
        result_handler.enum("state", Brewery, state_on=Brewery.MMMM)(value) == expected
    )
    check_for_error(value, expected, caplog.text, error.format(value))


@pytest.mark.parametrize(
    ("config", "error"),
    [
        (
            {"default_entity_id": "test.test"},
            "Received invalid test state: {} for entity test.test, expected: mmmm, beer, is, good, 0, false, no, off, disable",
        ),
        (
            {},
            "Received invalid state: {} for entity Test, expected: mmmm, beer, is, good, 0, false, no, off, disable",
        ),
    ],
)
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("mmmm", Brewery.MMMM),
        ("MmMM", Brewery.MMMM),
        ("mmMM", Brewery.MMMM),
        ("beer", Brewery.BEER),
        ("is", Brewery.IS),
        ("good", Brewery.GOOD),
        *expect_boolean_on(None),
        *expect_boolean_off(Brewery.BEER),
        *expect_none(
            None,
            "mm",
            "beeal;dfj",
            "unknown",
            "unavailable",
            "tru",  # codespell:ignore tru
            "7",
            "-1",
            {},
            {"junk": "stuff"},
            {"junk"},
            [],
            ["stuff"],
        ),
    ],
)
async def test_enum_with_off(
    hass: HomeAssistant,
    config: dict,
    error: str,
    value: Any,
    expected: bool | None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test enum with state_off validator."""
    result_handler = create_result_handler(hass, config)
    assert (
        result_handler.enum("state", Brewery, state_off=Brewery.BEER)(value) == expected
    )
    check_for_error(value, expected, caplog.text, error.format(value))


@pytest.mark.parametrize(
    ("config", "error"),
    [
        (
            {"default_entity_id": "test.test"},
            "Received invalid test state: {} for entity test.test, expected: 1, true, yes, on, enable, 0, false, no, off, disable",
        ),
        (
            {},
            "Received invalid state: {} for entity Test, expected: 1, true, yes, on, enable, 0, false, no, off, disable",
        ),
    ],
)
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        *expect_boolean_on(),
        *expect_boolean_off(),
        *expect_none(
            None,
            "al;dfj",
            "unknown",
            "unavailable",
            "tru",  # codespell:ignore tru
            "7",
            "-1",
            {},
            {"junk": "stuff"},
            {"junk"},
            [],
            ["stuff"],
        ),
    ],
)
async def test_boolean(
    hass: HomeAssistant,
    config: dict,
    error: str,
    value: Any,
    expected: bool | None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test boolean validator."""
    result_handler = create_result_handler(hass, config)
    assert result_handler.boolean("state")(value) == expected
    check_for_error(value, expected, caplog.text, error.format(value))


@pytest.mark.parametrize(
    ("config", "error"),
    [
        (
            {"default_entity_id": "test.test"},
            "Received invalid test state: {} for entity test.test, expected a number",
        ),
        (
            {},
            "Received invalid state: {} for entity Test, expected a number",
        ),
    ],
)
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("7.5", 7.5),
        ("0.0", 0.0),
        ("-324.4564", -324.4564),
        ("5e-4", 0.0005),
        ("5e4", 50000.0),
        (7.5, 7.5),
        (0.0, 0.0),
        (-324.4564, -324.4564),
        (1, 1.0),
        *expect_none(
            None,
            "al;dfj",
            "unknown",
            "unavailable",
            "tru",  # codespell:ignore tru
            True,
            False,
            {},
            {"junk": "stuff"},
            {"junk"},
            [],
            ["stuff"],
        ),
    ],
)
async def test_number_as_float(
    hass: HomeAssistant,
    config: dict,
    error: str,
    value: Any,
    expected: bool | None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test number validator."""
    result_handler = create_result_handler(hass, config)
    value = result_handler.number("state")(value)
    assert value == expected
    check_for_error(value, expected, caplog.text, error.format(value))


@pytest.mark.parametrize(
    ("config", "error"),
    [
        (
            {"default_entity_id": "test.test"},
            "Received invalid test state: {} for entity test.test, expected a number",
        ),
        (
            {},
            "Received invalid state: {} for entity Test, expected a number",
        ),
    ],
)
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("7.5", 7),
        ("0.0", 0),
        ("-324.4564", -324),
        ("5e-4", 0),
        ("5e4", 50000),
        (7.5, 7),
        (0.0, 0),
        (-324.4564, -324),
        (1, 1),
        *expect_none(
            None,
            "al;dfj",
            "unknown",
            "unavailable",
            "tru",  # codespell:ignore tru
            True,
            False,
            {},
            {"junk": "stuff"},
            {"junk"},
            [],
            ["stuff"],
        ),
    ],
)
async def test_number_as_int(
    hass: HomeAssistant,
    config: dict,
    error: str,
    value: Any,
    expected: bool | None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test number with return_type int validator."""
    result_handler = create_result_handler(hass, config)
    value = result_handler.number("state", return_type=int)(value)
    assert value == expected
    check_for_error(value, expected, caplog.text, error.format(value))


@pytest.mark.parametrize(
    ("config", "error"),
    [
        (
            {"default_entity_id": "test.test"},
            "Received invalid test state: {} for entity test.test, expected a number greater than or equal to 0.0",
        ),
        (
            {},
            "Received invalid state: {} for entity Test, expected a number greater than or equal to 0.0",
        ),
    ],
)
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("7.5", 7.5),
        ("0.0", 0),
        ("5e-4", 0.0005),
        ("5e4", 50000.0),
        (7.5, 7.5),
        (0.0, 0),
        (1, 1.0),
        *expect_none(
            None,
            "al;dfj",
            "unknown",
            "unavailable",
            "tru",  # codespell:ignore tru
            "-324.4564",
            -324.4564,
            "-0.00001",
            -0.00001,
            True,
            False,
            {},
            {"junk": "stuff"},
            {"junk"},
            [],
            ["stuff"],
        ),
    ],
)
async def test_number_with_minimum(
    hass: HomeAssistant,
    config: dict,
    error: str,
    value: Any,
    expected: bool | None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test number with minimum validator."""
    result_handler = create_result_handler(hass, config)
    value = result_handler.number("state", minimum=0.0)(value)
    assert value == expected
    check_for_error(value, expected, caplog.text, error.format(value))


@pytest.mark.parametrize(
    ("config", "error"),
    [
        (
            {"default_entity_id": "test.test"},
            "Received invalid test state: {} for entity test.test, expected a number less than or equal to 0.0",
        ),
        (
            {},
            "Received invalid state: {} for entity Test, expected a number less than or equal to 0.0",
        ),
    ],
)
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("-7.5", -7.5),
        ("0.0", 0),
        ("-5e-4", -0.0005),
        ("-5e4", -50000),
        (-7.5, -7.5),
        (0.0, 0.0),
        (-1, -1.0),
        *expect_none(
            None,
            "al;dfj",
            "unknown",
            "unavailable",
            "tru",  # codespell:ignore tru
            "324.4564",
            "0.00001",
            True,
            False,
            {},
            {"junk": "stuff"},
            {"junk"},
        ),
    ],
)
async def test_number_with_maximum(
    hass: HomeAssistant,
    config: dict,
    error: str,
    value: Any,
    expected: bool | None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test number with maximum validator."""
    result_handler = create_result_handler(hass, config)
    value = result_handler.number("state", maximum=0.0)(value)
    assert value == expected
    check_for_error(value, expected, caplog.text, error.format(value))


@pytest.mark.parametrize(
    ("config", "error"),
    [
        (
            {"default_entity_id": "test.test"},
            "Received invalid test state: {} for entity test.test, expected a number between 0.0 and 100.0",
        ),
        (
            {},
            "Received invalid state: {} for entity Test, expected a number between 0.0 and 100.0",
        ),
    ],
)
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("7.5", 7.5),
        ("0.0", 0),
        ("0.0012", 0.0012),
        ("99.0", 99.0),
        ("100", 100),
        *expect_none(
            None,
            "al;dfj",
            "unknown",
            "unavailable",
            "tru",  # codespell:ignore tru
            "324.4564",
            "-5e4101",
            True,
            False,
            {},
            {"junk": "stuff"},
            {"junk"},
        ),
    ],
)
async def test_number_in_range(
    hass: HomeAssistant,
    config: dict,
    error: str,
    value: Any,
    expected: bool | None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test number within a range validator."""
    result_handler = create_result_handler(hass, config)
    value = result_handler.number("state", minimum=0.0, maximum=100.0)(value)
    assert value == expected
    check_for_error(value, expected, caplog.text, error.format(value))


@pytest.mark.parametrize(
    ("config", "error"),
    [
        (
            {"default_entity_id": "test.test"},
            "Received invalid test state: {} for entity test.test, expected a list of strings",
        ),
        (
            {},
            "Received invalid state: {} for entity Test, expected a list of strings",
        ),
    ],
)
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (["beer", "is", "good"], ["beer", "is", "good"]),
        (["beer", None, True], ["beer", "None", "True"]),
        ([], []),
        (["99.0", 99.0, 99], ["99.0", "99.0", "99"]),
        *expect_none(
            None,
            "al;dfj",
            "unknown",
            "unavailable",
            "tru",  # codespell:ignore tru
            83242.2342,
            True,
            False,
            {},
            {"junk": "stuff"},
            {"junk"},
        ),
    ],
)
async def test_list_of_strings(
    hass: HomeAssistant,
    config: dict,
    error: str,
    value: Any,
    expected: bool | None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test result as a list of strings."""
    result_handler = create_result_handler(hass, config)
    value = result_handler.list_of_strings("state")(value)
    assert value == expected
    check_for_error(value, expected, caplog.text, error.format(value))


async def test_list_of_strings_none_on_empty(
    hass: HomeAssistant,
) -> None:
    """Test result as a list of strings with an empty list returning None."""
    result_handler = create_result_handler(hass, {"default_entity_id": "test.test"})
    value = result_handler.list_of_strings("state", none_on_empty=True)([])
    assert value is None


@pytest.mark.parametrize(
    ("config", "error"),
    [
        (
            {"default_entity_id": "test.test"},
            "Received invalid test state: {} for entity test.test, expected beer, is, GOOD",
        ),
        (
            {},
            "Received invalid state: {} for entity Test, expected beer, is, GOOD",
        ),
    ],
)
@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("beer", "beer"),
        ("is", "is"),
        ("GOOD", "GOOD"),
        *expect_none(
            None,
            "BEER",
            "IS",
            "good",
            "al;dfj",
            "unknown",
            "unavailable",
            "tru",  # codespell:ignore tru
            83242.2342,
            True,
            False,
            {},
            {"junk": "stuff"},
            {"junk"},
        ),
    ],
)
async def test_item_in_list(
    hass: HomeAssistant,
    config: dict,
    error: str,
    value: Any,
    expected: bool | None,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test result is in a list."""
    result_handler = create_result_handler(hass, config)
    value = result_handler.item_in_list("state", ["beer", "is", "GOOD"])(value)
    assert value == expected
    check_for_error(value, expected, caplog.text, error.format(value))


@pytest.mark.parametrize(
    ("config", "error"),
    [
        (
            {"default_entity_id": "test.test"},
            "Received invalid test state: {} for entity test.test, expected: beer, is, GOOD",
        ),
        (
            {},
            "Received invalid state: {} for entity Test, expected: beer, is, GOOD",
        ),
    ],
)
async def test_item_in_list_changes(
    hass: HomeAssistant,
    config: dict,
    error: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test test an item is in a list after the list changes."""
    result_handler = create_result_handler(hass, config)
    items = ["beer", "is", "GOOD"]
    value = result_handler.item_in_list("state", items)("mmmm")
    assert value is None
    assert error.format("mmmm") in caplog.text

    items.append("mmmm")

    value = result_handler.item_in_list("state", items)("mmmm")
    assert value == "mmmm"
    assert error.format(value) + ", mmmm" not in caplog.text
