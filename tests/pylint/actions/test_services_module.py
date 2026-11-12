"""Tests for the services module checker."""

import astroid
from astroid import nodes
from pylint.testutils import MessageTest, UnittestLinter
from pylint_home_assistant.checkers.actions.services_module import ServicesModuleChecker
import pytest

from tests.pylint import assert_adds_messages, assert_no_messages, walk_checker

SERVICES_MODULE = "homeassistant.components.test_integration.services"


@pytest.fixture(name="services_module_checker")
def services_module_checker_fixture(
    linter: UnittestLinter,
) -> ServicesModuleChecker:
    """Fixture to provide a services module checker."""
    return ServicesModuleChecker(linter)


@pytest.mark.parametrize(
    ("code", "module_name"),
    [
        pytest.param(
            """
@callback
def async_setup_services(hass):
    hass.services.async_register(DOMAIN, "my_action", _handler)
    async_register_admin_service(hass, DOMAIN, "admin_action", _handler)
    service.async_register_platform_entity_service(
        hass, DOMAIN, "entity_action", entity_domain=LIGHT_DOMAIN, func="method"
    )
""",
            SERVICES_MODULE,
            id="async_setup_services",
        ),
        pytest.param(
            """
def setup_services(hass):
    hass.services.register(DOMAIN, "my_action", _handler)
""",
            SERVICES_MODULE,
            id="setup_services",
        ),
        pytest.param(
            """
@callback
def async_setup_services(hass):
    _register_more(hass)

def _register_more(hass):
    _register_even_more(hass)

def _register_even_more(hass):
    hass.services.async_register(DOMAIN, "my_action", _handler)
""",
            SERVICES_MODULE,
            id="helper_called_from_async_setup_services",
        ),
        pytest.param(
            """
def setup_services(hass):
    _register_more(hass)

def _register_more(hass):
    hass.services.register(DOMAIN, "my_action", _handler)
""",
            SERVICES_MODULE,
            id="helper_called_from_setup_services",
        ),
        pytest.param(
            """
@core.callback
def async_setup_services(hass):
    def _register() -> None:
        hass.services.async_register(DOMAIN, "my_action", _handler)

    _register()
""",
            SERVICES_MODULE,
            id="nested_function_in_async_setup_services",
        ),
        pytest.param(
            """
async def async_setup_entry(hass, entry):
    hass.services.async_register(DOMAIN, "my_action", handler)
""",
            "tests.components.test_integration",
            id="not_integration_module",
        ),
    ],
)
def test_no_warning(
    linter: UnittestLinter,
    services_module_checker: ServicesModuleChecker,
    code: str,
    module_name: str,
) -> None:
    """Test cases that should not trigger a warning."""
    root_node = astroid.parse(code, module_name)

    with assert_no_messages(linter):
        walk_checker(linter, services_module_checker, root_node)


@pytest.mark.parametrize(
    ("code", "module_name", "line"),
    [
        pytest.param(
            """
async def async_setup(hass, config):
    hass.services.async_register(DOMAIN, "my_action", handler)
""",
            "homeassistant.components.test_integration",
            3,
            id="in_init",
        ),
        pytest.param(
            """
def setup(hass, config):
    hass.services.register(DOMAIN, "my_action", handler)
""",
            "homeassistant.components.test_integration",
            3,
            id="sync_register_in_init",
        ),
        pytest.param(
            """
async def async_setup(hass, config):
    service.async_register_batched_platform_entity_service(
        hass, DOMAIN, "my_action", entity_domain=MP_DOMAIN, func=handler
    )
""",
            "homeassistant.components.test_integration",
            3,
            id="batched_platform_entity_service_in_init",
        ),
        pytest.param(
            """
async def async_setup_entry(hass, entry, async_add_entities):
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service("my_action", {}, "async_method")
""",
            "homeassistant.components.test_integration.light",
            4,
            id="entity_service_in_platform",
        ),
        pytest.param(
            """
@callback
def async_setup_services(hass):
    hass.services.async_register(DOMAIN, "my_action", handler)
""",
            "homeassistant.components.test_integration.helpers",
            4,
            id="async_setup_services_outside_services_module",
        ),
        pytest.param(
            """
@callback
def register_actions(hass):
    hass.services.async_register(DOMAIN, "my_action", handler)
""",
            SERVICES_MODULE,
            4,
            id="other_function_in_services_module",
        ),
        pytest.param(
            """
@callback
def async_setup_services(hass):
    pass

def _register_more(hass):
    hass.services.async_register(DOMAIN, "my_action", handler)
""",
            SERVICES_MODULE,
            7,
            id="helper_not_called_from_setup",
        ),
        pytest.param(
            """
class Actions:
    def async_register(self):
        self.hass.services.async_register(DOMAIN, "my_action", self.handler)

@callback
def async_setup_services(hass):
    Actions(hass).async_register()
""",
            SERVICES_MODULE,
            4,
            id="class_method",
        ),
        pytest.param(
            """
@callback
def async_setup_services(hass):
    hass.async_create_task(_async_register(hass))

async def _async_register(hass):
    hass.services.async_register(DOMAIN, "my_action", handler)
""",
            SERVICES_MODULE,
            7,
            id="async_helper_called_from_setup",
        ),
    ],
)
def test_registration_outside_services_module(
    linter: UnittestLinter,
    services_module_checker: ServicesModuleChecker,
    code: str,
    module_name: str,
    line: int,
) -> None:
    """Test that registrations outside the setup functions are flagged."""
    root_node = astroid.parse(code, module_name)
    call = next(
        node for node in root_node.nodes_of_class(nodes.Call) if node.lineno == line
    )

    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="home-assistant-action-registered-outside-services-module",
            node=call,
            line=call.lineno,
            col_offset=call.col_offset,
            end_line=call.end_lineno,
            end_col_offset=call.end_col_offset,
        ),
    ):
        walk_checker(linter, services_module_checker, root_node)


@pytest.mark.parametrize(
    ("code", "args"),
    [
        pytest.param(
            """
def async_setup_services(hass):
    pass
""",
            ("async_setup_services", " decorated with `@callback`"),
            id="async_setup_services_not_callback",
        ),
        pytest.param(
            """
@callback
async def async_setup_services(hass):
    pass
""",
            ("async_setup_services", " decorated with `@callback`"),
            id="async_setup_services_coroutine",
        ),
        pytest.param(
            """
@callback
def async_setup_services(hass, config):
    pass
""",
            ("async_setup_services", " decorated with `@callback`"),
            id="async_setup_services_extra_argument",
        ),
        pytest.param(
            """
@callback
def setup_services(hass):
    pass
""",
            ("setup_services", " not decorated with `@callback`"),
            id="setup_services_callback",
        ),
        pytest.param(
            """
def setup_services(hass, *, config):
    pass
""",
            ("setup_services", " not decorated with `@callback`"),
            id="setup_services_extra_argument",
        ),
    ],
)
def test_invalid_setup_services(
    linter: UnittestLinter,
    services_module_checker: ServicesModuleChecker,
    code: str,
    args: tuple[str, str],
) -> None:
    """Test that setup functions with a wrong signature are flagged."""
    root_node = astroid.parse(code, SERVICES_MODULE)
    function = root_node.body[0]

    with assert_adds_messages(
        linter,
        MessageTest(
            msg_id="home-assistant-invalid-setup-services",
            node=function,
            args=args,
            line=function.position.lineno,
            col_offset=function.position.col_offset,
            end_line=function.position.end_lineno,
            end_col_offset=function.position.end_col_offset,
        ),
    ):
        walk_checker(linter, services_module_checker, root_node)
