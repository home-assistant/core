"""Tests for the service registration checker."""

import astroid
from pylint.testutils import UnittestLinter
from pylint.utils.ast_walker import ASTWalker
from pylint_home_assistant.checkers.actions.service_registration import (
    ServiceRegistrationChecker,
)
import pytest

from tests.pylint import assert_no_messages


@pytest.fixture(name="registration_checker")
def registration_checker_fixture(
    linter: UnittestLinter,
) -> ServiceRegistrationChecker:
    """Fixture to provide a service registration checker."""
    return ServiceRegistrationChecker(linter)


@pytest.mark.parametrize(
    ("code", "module_name"),
    [
        pytest.param(
            """
async def async_setup(hass, config):
    hass.services.async_register(DOMAIN, "my_service", handler)

async def async_setup_entry(hass, entry):
    pass
""",
            "homeassistant.components.test_integration",
            id="registered_in_async_setup",
        ),
        pytest.param(
            """
async def async_setup_entry(hass, entry):
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
""",
            "homeassistant.components.test_integration",
            id="no_service_registration",
        ),
        pytest.param(
            """
async def async_setup_entry(hass, entry, async_add_entities):
    platform = entity_platform.async_get_current_platform()
    platform.async_register_entity_service("set_speed", {}, "async_set_speed")
""",
            "homeassistant.components.test_integration.fan",
            id="entity_service_in_platform_setup_entry",
        ),
        pytest.param(
            """
async def async_setup_entry(hass, entry):
    hass.services.async_register(DOMAIN, "my_service", handler)
""",
            "tests.components.test_integration",
            id="not_integration_module",
        ),
    ],
)
def test_no_warning(
    linter: UnittestLinter,
    registration_checker: ServiceRegistrationChecker,
    code: str,
    module_name: str,
) -> None:
    """Test cases that should not trigger a warning."""
    root_node = astroid.parse(code, module_name)
    walker = ASTWalker(linter)
    walker.add_checker(registration_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


def test_hass_services_register_flagged(
    linter: UnittestLinter,
    registration_checker: ServiceRegistrationChecker,
) -> None:
    """Test that hass.services.async_register in async_setup_entry is flagged."""
    root_node = astroid.parse(
        """
async def async_setup_entry(hass, entry):
    hass.services.async_register(DOMAIN, "my_service", handler)
""",
        "homeassistant.components.test_integration",
    )
    walker = ASTWalker(linter)
    walker.add_checker(registration_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-service-registered-in-setup-entry"


def test_hass_services_sync_register_flagged(
    linter: UnittestLinter,
    registration_checker: ServiceRegistrationChecker,
) -> None:
    """Test that hass.services.register (sync form) is also flagged."""
    root_node = astroid.parse(
        """
async def async_setup_entry(hass, entry):
    hass.services.register(DOMAIN, "my_service", handler)
""",
        "homeassistant.components.test_integration",
    )
    walker = ASTWalker(linter)
    walker.add_checker(registration_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1


def test_admin_service_bare_name_flagged(
    linter: UnittestLinter,
    registration_checker: ServiceRegistrationChecker,
) -> None:
    """Test that async_register_admin_service (bare name) is flagged."""
    root_node = astroid.parse(
        """
async def async_setup_entry(hass, entry):
    async_register_admin_service(hass, DOMAIN, "reset", handler)
""",
        "homeassistant.components.test_integration",
    )
    walker = ASTWalker(linter)
    walker.add_checker(registration_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1


def test_admin_service_attribute_form_flagged(
    linter: UnittestLinter,
    registration_checker: ServiceRegistrationChecker,
) -> None:
    """Test that service.async_register_admin_service is flagged."""
    root_node = astroid.parse(
        """
async def async_setup_entry(hass, entry):
    service.async_register_admin_service(hass, DOMAIN, "reset", handler)
""",
        "homeassistant.components.test_integration",
    )
    walker = ASTWalker(linter)
    walker.add_checker(registration_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1


def test_multiple_registrations_flagged(
    linter: UnittestLinter,
    registration_checker: ServiceRegistrationChecker,
) -> None:
    """Test that multiple registrations are each flagged."""
    root_node = astroid.parse(
        """
async def async_setup_entry(hass, entry):
    hass.services.async_register(DOMAIN, "service_a", handler_a)
    hass.services.async_register(DOMAIN, "service_b", handler_b)
    async_register_admin_service(hass, DOMAIN, "admin_svc", handler_c)
""",
        "homeassistant.components.test_integration",
    )
    walker = ASTWalker(linter)
    walker.add_checker(registration_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 3


def test_helper_function_flagged(
    linter: UnittestLinter,
    registration_checker: ServiceRegistrationChecker,
) -> None:
    """Test services in helper functions called from setup are flagged."""
    root_node = astroid.parse(
        """
def _register_services(hass):
    hass.services.async_register(DOMAIN, "my_service", handler)

async def async_setup_entry(hass, entry):
    _register_services(hass)
""",
        "homeassistant.components.test_integration",
    )
    walker = ASTWalker(linter)
    walker.add_checker(registration_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1


def test_helper_function_not_from_setup_entry(
    linter: UnittestLinter,
    registration_checker: ServiceRegistrationChecker,
) -> None:
    """Test that helper functions called from async_setup (not entry) are fine."""
    root_node = astroid.parse(
        """
def _register_services(hass):
    hass.services.async_register(DOMAIN, "my_service", handler)

async def async_setup(hass, config):
    _register_services(hass)

async def async_setup_entry(hass, entry):
    pass
""",
        "homeassistant.components.test_integration",
    )
    walker = ASTWalker(linter)
    walker.add_checker(registration_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)
