"""Test that YAML source annotations survive Home Assistant's config pipeline.

The loader (annotatedyaml), the validation engine (probatio) and the readers in
homeassistant.config are three separate packages, and what breaks in production
is their composition: a location the loader recorded is read back after a schema
has run. No single package's test suite covers that, so it lives here rather
than next to any one helper.
"""

from collections.abc import Callable, Generator
import os
from typing import Any

from probatio import (
    Coerce,
    CompilePolicy,
    Schema,
    get_compile_policy,
    set_compile_policy,
)
import pytest

from homeassistant import config as config_util
from homeassistant.config import _get_annotation, find_annotation
from homeassistant.core import HomeAssistant
from homeassistant.util.yaml.objects import NodeDictClass

from .common import get_fixture_path

CONFIG_DIR = str(get_fixture_path("core/config/annotations/basic"))
CONFIGURATION_YAML = os.path.join(CONFIG_DIR, "configuration.yaml")
INCLUDED_YAML = os.path.join(CONFIG_DIR, "included.yaml")

CONTAINER_XFAIL = pytest.mark.xfail(
    strict=True,
    reason=(
        "probatio's mapping and sequence engines rebuild the container as a fresh "
        "instance of the input's class, so the __config_file__/__line__ slots "
        "annotatedyaml set on the original are never copied."
    ),
)


@pytest.fixture(
    params=[CompilePolicy.OFF, CompilePolicy.ON],
    ids=["interpreted", "generated"],
)
def probatio_compile_policy(request: pytest.FixtureRequest) -> Generator[None]:
    """Run the test against the interpreted and the generated validator.

    The generated validator bails back to the interpreted engine for anything
    that is not exactly a dict or a list, so a node class takes the same
    interpreted rebuild under either policy today. Running both is what guards
    that bail-out: if generated code ever handled dict subclasses inline without
    copying the slots, only the generated case would move.

    OFF and ON are pinned rather than the AUTO default because AUTO switches from
    one to the other after a call count probatio keeps internal and does not
    export.
    """
    original = get_compile_policy()
    set_compile_policy(request.param)
    yield
    set_compile_policy(original)


@pytest.fixture
async def annotated_config(hass: HomeAssistant) -> dict:
    """Load the annotations fixture directory the way Home Assistant loads it."""
    hass.config.config_dir = CONFIG_DIR
    return await config_util.async_hass_config_yaml(hass)


def _key(mapping: dict, name: str) -> Any:
    """Return the key object of mapping equal to name."""
    return next(key for key in mapping if key == name)


def _schema() -> Schema:
    """Return a schema for the fixture config, built fresh so the policy applies."""
    domain = {"mars": str, "servers": [{"port": int, "name": str}]}
    return Schema({"test_domain": domain, "included_domain": domain})


async def test_loader_annotates_every_container(annotated_config: dict) -> None:
    """Test the loader records a distinct file and line at each nesting depth.

    Precondition for the rest of the module: if this fails the fixture config is
    broken rather than the carry.
    """
    assert _get_annotation(annotated_config) == (CONFIGURATION_YAML, 1)
    assert _get_annotation(annotated_config["test_domain"]) == (CONFIGURATION_YAML, 2)
    assert _get_annotation(annotated_config["test_domain"]["servers"]) == (
        CONFIGURATION_YAML,
        4,
    )
    assert _get_annotation(annotated_config["test_domain"]["servers"][1]) == (
        CONFIGURATION_YAML,
        6,
    )
    assert _get_annotation(annotated_config["included_domain"]["servers"]) == (
        INCLUDED_YAML,
        3,
    )


@pytest.mark.usefixtures("probatio_compile_policy")
async def test_validation_keeps_the_node_class(annotated_config: dict) -> None:
    """Test a rebuilt container is still a node class; only the location is dropped.

    Pinning the class separately keeps the two halves of the bug apart: an
    annotation assertion that fails because the class changed would be a
    different defect than the one the xfails below describe.
    """
    validated = _schema()(annotated_config)

    assert type(validated) is NodeDictClass
    assert type(validated["test_domain"]) is NodeDictClass
    assert type(validated["test_domain"]["servers"][1]) is NodeDictClass
    assert type(validated["included_domain"]) is NodeDictClass


@pytest.mark.parametrize(
    ("select", "expected"),
    [
        pytest.param(
            lambda config: _key(config, "test_domain"),
            (CONFIGURATION_YAML, 1),
            id="key_at_root",
        ),
        pytest.param(
            lambda config: _key(config["test_domain"], "servers"),
            (CONFIGURATION_YAML, 3),
            id="key_in_nested_dict",
        ),
        pytest.param(
            lambda config: _key(config["test_domain"]["servers"][1], "name"),
            (CONFIGURATION_YAML, 7),
            id="key_in_list_element",
        ),
        pytest.param(
            lambda config: _key(config["included_domain"], "servers"),
            (INCLUDED_YAML, 2),
            id="key_in_included_file",
        ),
        pytest.param(
            lambda config: config["test_domain"]["mars"],
            (CONFIGURATION_YAML, 2),
            id="scalar_value",
        ),
        pytest.param(
            lambda config: config,
            (CONFIGURATION_YAML, 1),
            marks=CONTAINER_XFAIL,
            id="root_dict",
        ),
        pytest.param(
            lambda config: config["test_domain"],
            (CONFIGURATION_YAML, 2),
            marks=CONTAINER_XFAIL,
            id="dict_in_dict",
        ),
        pytest.param(
            lambda config: config["test_domain"]["servers"],
            (CONFIGURATION_YAML, 4),
            marks=CONTAINER_XFAIL,
            id="list_in_dict",
        ),
        pytest.param(
            lambda config: config["test_domain"]["servers"][1],
            (CONFIGURATION_YAML, 6),
            marks=CONTAINER_XFAIL,
            id="dict_in_list",
        ),
        pytest.param(
            lambda config: config["included_domain"]["servers"],
            (INCLUDED_YAML, 3),
            marks=CONTAINER_XFAIL,
            id="list_in_included_file",
        ),
    ],
)
@pytest.mark.usefixtures("probatio_compile_policy")
async def test_annotation_survives_validation(
    annotated_config: dict,
    select: Callable[[dict], Any],
    expected: tuple[str, int],
) -> None:
    """Test a schema rebuild keeps the file and line the loader recorded.

    The key and scalar cases pass today because probatio stores the original key
    and value objects in the rebuilt mapping, which is why config error messages
    still carry locations at all; the container cases are the bug. The two
    included-file cases pin the file as well as the line, so an annotation that
    survives pointing at the including file would still fail.
    """
    validated = _schema()(annotated_config)

    assert _get_annotation(select(validated)) == expected


async def test_type_check_schema_returns_the_same_object(
    annotated_config: dict,
) -> None:
    """Test Schema(dict) checks the type and rebuilds nothing, so nothing is lost.

    This separates "the rebuild dropped the location" from "going through a
    schema dropped the location".
    """
    validated = Schema(dict)(annotated_config)

    assert validated is annotated_config
    assert _get_annotation(validated) == (CONFIGURATION_YAML, 1)


async def test_coerce_loses_the_annotation(annotated_config: dict) -> None:
    """Test Coerce builds a plain dict, which has no slot to hold a location.

    Asserted as it behaves rather than xfailed: this loss is inherent to the
    target type, so an upstream change that started preserving it is a surprise
    worth being told about.
    """
    validated = Schema(Coerce(dict))(annotated_config)

    assert type(validated) is dict
    assert _get_annotation(validated) is None


async def test_rebuilding_validator_loses_the_annotation(
    annotated_config: dict,
) -> None:
    """Test a validator rebuilding via type(value)(...) keeps the class, not the location.

    Asserted as it behaves rather than xfailed: preserving the class is not
    preserving the annotation, and a validator that rebuilds has to carry the
    location itself.
    """

    def rebuild(value: NodeDictClass) -> NodeDictClass:
        return type(value)((key, item) for key, item in value.items())

    validated = Schema(rebuild)(annotated_config)

    assert type(validated) is NodeDictClass
    assert _get_annotation(validated) is None


@pytest.mark.parametrize(
    ("path", "expected"),
    [
        pytest.param(["test_domain", "mars"], (CONFIGURATION_YAML, 2), id="own_key"),
        pytest.param(
            ["test_domain", "servers"], (CONFIGURATION_YAML, 3), id="parent_key"
        ),
        pytest.param(
            ["included_domain", "servers"],
            (INCLUDED_YAML, 2),
            id="key_in_included_file",
        ),
        pytest.param(
            [], (CONFIGURATION_YAML, 1), marks=CONTAINER_XFAIL, id="root_has_no_key"
        ),
        pytest.param(
            ["test_domain", "servers", 0],
            (CONFIGURATION_YAML, 4),
            marks=CONTAINER_XFAIL,
            id="list_element_has_no_key",
        ),
    ],
)
@pytest.mark.usefixtures("probatio_compile_policy")
async def test_find_annotation_after_validation(
    annotated_config: dict, path: list[str | int], expected: tuple[str, int]
) -> None:
    """Test find_annotation reads the key first, so it only fails where no key is reachable.

    The list element case reports the line of the "servers:" key today instead of
    the line of the element itself.
    """
    validated = _schema()(annotated_config)

    assert find_annotation(validated, path) == expected
