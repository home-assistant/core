"""Tests for the services module checker."""

import astroid
from pylint.testutils import UnittestLinter
from pylint_home_assistant.checkers.actions.services_module import ServicesModuleChecker
import pytest

from tests.pylint import assert_no_messages, walk_checker

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
    ("code", "module_name"),
    [
        pytest.param(
            """
async def async_setup(hass, config):
    hass.services.async_register(DOMAIN, "my_action", handler)
""",
            "homeassistant.components.test_integration",
            id="in_init",
        ),
        pytest.param(
            """
def setup(hass, config):
    hass.services.register(DOMAIN, "my_action", handler)
""",
            "homeassistant.components.test_integration",
            id="sync_register_in_init",
        ),
        pytest.param(
            """
async def async_setup_entry(hass, entry, async_add_entities):
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service("my_action", {}, "async_method")
""",
            "homeassistant.components.test_integration.light",
            id="entity_service_in_platform",
        ),
        pytest.param(
            """
@callback
def async_setup_services(hass):
    hass.services.async_register(DOMAIN, "my_action", handler)
""",
            "homeassistant.components.test_integration.helpers",
            id="async_setup_services_outside_services_module",
        ),
        pytest.param(
            """
@callback
def register_actions(hass):
    hass.services.async_register(DOMAIN, "my_action", handler)
""",
            SERVICES_MODULE,
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
            id="class_method",
        ),
    ],
)
def test_registration_outside_services_module(
    linter: UnittestLinter,
    services_module_checker: ServicesModuleChecker,
    code: str,
    module_name: str,
) -> None:
    """Test that registrations outside the setup functions are flagged."""
    root_node = astroid.parse(code, module_name)
    walk_checker(linter, services_module_checker, root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert (
        messages[0].msg_id == "home-assistant-action-registered-outside-services-module"
    )


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
            ("setup_services", ""),
            id="setup_services_callback",
        ),
        pytest.param(
            """
def setup_services(hass, *, config):
    pass
""",
            ("setup_services", ""),
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
    walk_checker(linter, services_module_checker, root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-invalid-setup-services"
    assert messages[0].args == args
