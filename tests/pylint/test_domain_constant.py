"""Tests for the domain constant checker."""

import astroid
from pylint.testutils import UnittestLinter
from pylint.utils.ast_walker import ASTWalker
from pylint_home_assistant.checkers.domain_constant import DomainConstantChecker
import pytest

from . import assert_no_messages


@pytest.fixture(name="domain_constant_checker")
def domain_constant_checker_fixture(
    linter: UnittestLinter,
) -> DomainConstantChecker:
    """Fixture to provide a domain constant checker."""
    return DomainConstantChecker(linter)


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            """
async_setup_component(hass, DOMAIN, {})
""",
            id="name_domain_constant",
        ),
        pytest.param(
            """
async_setup_component(hass, domain, {})
""",
            id="name_domain_variable",
        ),
        pytest.param(
            """
async_setup_component(hass, SENSOR_DOMAIN, {})
""",
            id="name_prefixed_domain_constant",
        ),
        pytest.param(
            """
async_setup_component(hass, sensor_domain, {})
""",
            id="name_prefixed_domain_variable",
        ),
        pytest.param(
            """
async_setup_component(hass, sensor.DOMAIN, {})
""",
            id="attribute_domain_constant",
        ),
        pytest.param(
            """
async_setup_component(hass, config_entry.domain, {})
""",
            id="attribute_domain",
        ),
        pytest.param(
            """
async_setup_component(hass, sensor.SENSOR_DOMAIN, {})
""",
            id="attribute_prefixed_domain_constant",
        ),
        pytest.param(
            """
async_setup_component(hass, "sensor", {})
""",
            id="string_literal",
        ),
        pytest.param(
            """
async_setup_component(hass, config["domain"], {})
""",
            id="subscript_positional",
        ),
        pytest.param(
            """
MockConfigEntry(domain=entries["domain"])
""",
            id="subscript_kwarg",
        ),
        pytest.param(
            """
async_mock_service(hass, DOMAIN, "service")
""",
            id="async_mock_service",
        ),
        pytest.param(
            """
MockConfigEntry(domain=DOMAIN)
""",
            id="mock_config_entry_kwarg",
        ),
        pytest.param(
            """
MockConfigEntry("other")
""",
            id="mock_config_entry_positional_not_checked",
        ),
        pytest.param(
            """
hass.services.async_call(DOMAIN, "service")
""",
            id="services_async_call",
        ),
        pytest.param(
            """
hass.services.call(DOMAIN, "service")
""",
            id="services_call",
        ),
        pytest.param(
            """
hass.config_entries.flow.async_init(DOMAIN)
""",
            id="flow_async_init_positional",
        ),
        pytest.param(
            """
hass.config_entries.flow.async_init(handler=DOMAIN)
""",
            id="flow_async_init_kwarg",
        ),
        pytest.param(
            """
hass.states.async_entity_ids(DOMAIN)
""",
            id="async_entity_ids",
        ),
        pytest.param(
            """
hass.states.async_entity_ids((DOMAIN, SENSOR_DOMAIN))
""",
            id="async_entity_ids_tuple",
        ),
        pytest.param(
            """
some_other_function(hass, "other", {})
""",
            id="unrelated_function",
        ),
        pytest.param(
            """
hass.services.unrelated("other")
""",
            id="unrelated_method",
        ),
        pytest.param(
            """
async_setup_component(hass, OTHER, {})
""",
            id="name_not_domain",
        ),
        pytest.param(
            """
async_setup_component(hass, sensor.OTHER, {})
""",
            id="attribute_not_domain",
        ),
        pytest.param(
            """
async_setup_component(hass, 5, {})
""",
            id="non_string_constant",
        ),
        pytest.param(
            """
async_mock_service(hass, OTHER, "service")
""",
            id="async_mock_service_other",
        ),
        pytest.param(
            """
MockConfigEntry(domain=OTHER)
""",
            id="mock_config_entry_kwarg_other",
        ),
        pytest.param(
            """
hass.services.async_call(OTHER, "service")
""",
            id="services_async_call_other",
        ),
        pytest.param(
            """
hass.services.call(OTHER, "service")
""",
            id="services_call_other",
        ),
        pytest.param(
            """
hass.config_entries.flow.async_init(OTHER)
""",
            id="flow_async_init_positional_other",
        ),
        pytest.param(
            """
hass.config_entries.flow.async_init(handler=OTHER)
""",
            id="flow_async_init_kwarg_other",
        ),
        pytest.param(
            """
hass.states.async_entity_ids(OTHER)
""",
            id="async_entity_ids_other",
        ),
        pytest.param(
            """
hass.states.async_entity_ids((DOMAIN, OTHER))
""",
            id="async_entity_ids_tuple_other",
        ),
    ],
)
def test_no_warning(
    linter: UnittestLinter,
    domain_constant_checker: DomainConstantChecker,
    code: str,
) -> None:
    """Test cases that should not trigger a warning."""
    root_node = astroid.parse(code, "tests.components.test_integration.test_init")
    walker = ASTWalker(linter)
    walker.add_checker(domain_constant_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


@pytest.mark.parametrize(
    ("code", "args"),
    [
        pytest.param(
            """
async_setup_component(hass, Platform.Something, {})
""",
            ("Platform.Something", "async_setup_component"),
            id="attribute_platform",
        ),
        pytest.param(
            """
hass.states.async_entity_ids((Platform.SENSOR, DOMAIN))
""",
            ("(Platform.SENSOR, DOMAIN)", "hass.states.async_entity_ids"),
            id="attribute_platform_tuple",
        ),
    ],
)
def test_domain_argument_flagged(
    linter: UnittestLinter,
    domain_constant_checker: DomainConstantChecker,
    code: str,
    args: tuple[str, str],
) -> None:
    """Test that non-domain arguments are flagged."""
    root_node = astroid.parse(code, "tests.components.test_integration.test_init")
    walker = ASTWalker(linter)
    walker.add_checker(domain_constant_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-domain-argument"
    assert messages[0].args == args


def test_not_test_module_ignored(
    linter: UnittestLinter,
    domain_constant_checker: DomainConstantChecker,
) -> None:
    """Test that modules outside tests are ignored."""
    root_node = astroid.parse(
        """
async_setup_component(hass, OTHER, {})
""",
        "homeassistant.components.test_integration",
    )
    walker = ASTWalker(linter)
    walker.add_checker(domain_constant_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)
