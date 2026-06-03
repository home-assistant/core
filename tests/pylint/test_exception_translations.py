"""Tests for the exception translations checker."""

import json
from pathlib import Path

import astroid
from pylint.testutils import UnittestLinter
from pylint.utils.ast_walker import ASTWalker
from pylint_home_assistant.checkers.exception_translations import (
    ExceptionTranslationsChecker,
)
from pylint_home_assistant.helpers.quality_scale import clear_quality_scale_cache
from pylint_home_assistant.helpers.translations import clear_translations_cache
import pytest
import yaml

from . import assert_no_messages

# Pre-load so astroid can resolve exception classes in parsed snippets.
astroid.MANAGER.ast_from_module_name("homeassistant.exceptions")

_HA_IMPORTS = (
    "from homeassistant.exceptions import ("
    "HomeAssistantError, ServiceValidationError, ConfigEntryAuthFailed)"
)


@pytest.fixture(name="translations_checker")
def translations_checker_fixture(
    linter: UnittestLinter,
) -> ExceptionTranslationsChecker:
    """Fixture to provide an exception translations checker."""
    clear_translations_cache()
    clear_quality_scale_cache()
    return ExceptionTranslationsChecker(linter)


def _make_integration(
    tmp_path: Path,
    exceptions: dict | None = None,
    *,
    exception_translations_done: bool = False,
) -> Path:
    """Create a fake integration with optional strings.json."""
    integration_dir = tmp_path / "homeassistant" / "components" / "test_int"
    integration_dir.mkdir(parents=True)
    if exceptions is not None:
        strings = {"exceptions": exceptions}
        (integration_dir / "strings.json").write_text(json.dumps(strings))
    if exception_translations_done:
        qs = {"rules": {"exception-translations": "done"}}
        (integration_dir / "quality_scale.yaml").write_text(yaml.dump(qs))
    return integration_dir


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            f"""
{_HA_IMPORTS}
raise HomeAssistantError(
    translation_domain=DOMAIN,
    translation_key="some_error",
)
""",
            id="translated_no_placeholders",
        ),
        pytest.param(
            f"""
{_HA_IMPORTS}
raise HomeAssistantError(
    translation_domain=DOMAIN,
    translation_key="error_with_name",
    translation_placeholders={{"name": device_name}},
)
""",
            id="translated_with_placeholders",
        ),
        pytest.param(
            f"""
{_HA_IMPORTS}
raise ServiceValidationError(
    translation_domain=DOMAIN,
    translation_key="invalid_input",
)
""",
            id="service_validation_error_translated",
        ),
        pytest.param(
            f"""
{_HA_IMPORTS}
raise ConfigEntryAuthFailed(
    translation_domain=DOMAIN,
    translation_key="invalid_api_key",
)
""",
            id="config_entry_auth_failed_translated",
        ),
        pytest.param(
            f"""
{_HA_IMPORTS}
raise HomeAssistantError()
""",
            id="no_args_no_translation",
        ),
    ],
)
def test_no_warning(
    linter: UnittestLinter,
    translations_checker: ExceptionTranslationsChecker,
    tmp_path: Path,
    code: str,
) -> None:
    """Test cases that should not trigger a warning."""
    integration_dir = _make_integration(
        tmp_path,
        exceptions={
            "some_error": {"message": "An error occurred"},
            "error_with_name": {"message": "Error for {name}"},
            "invalid_input": {"message": "Invalid input"},
            "invalid_api_key": {"message": "Invalid API key"},
        },
    )
    root_node = astroid.parse(code, "homeassistant.components.test_int.coordinator")
    root_node.file = str(integration_dir / "coordinator.py")

    walker = ASTWalker(linter)
    walker.add_checker(translations_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


@pytest.mark.parametrize(
    ("exc_class", "code"),
    [
        pytest.param(
            "HomeAssistantError",
            f'{_HA_IMPORTS}\nraise HomeAssistantError("Something went wrong")',
            id="ha_error_hardcoded",
        ),
        pytest.param(
            "ServiceValidationError",
            f'{_HA_IMPORTS}\nraise ServiceValidationError("Invalid value")',
            id="service_validation_hardcoded",
        ),
        pytest.param(
            "ConfigEntryAuthFailed",
            f'{_HA_IMPORTS}\nraise ConfigEntryAuthFailed("Bad credentials")',
            id="auth_failed_hardcoded",
        ),
    ],
)
def test_hardcoded_string_flagged(
    linter: UnittestLinter,
    translations_checker: ExceptionTranslationsChecker,
    tmp_path: Path,
    exc_class: str,
    code: str,
) -> None:
    """Test that hardcoded string exceptions are flagged when quality scale rule is done."""
    integration_dir = _make_integration(tmp_path, exception_translations_done=True)
    root_node = astroid.parse(code, "homeassistant.components.test_int.coordinator")
    root_node.file = str(integration_dir / "coordinator.py")

    walker = ASTWalker(linter)
    walker.add_checker(translations_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-exception-not-translated"
    assert exc_class in messages[0].args[0]


@pytest.mark.parametrize(
    "code",
    [
        pytest.param(
            f"""
{_HA_IMPORTS}
raise HomeAssistantError(
    translation_key="some_error",
)
""",
            id="key_without_domain",
        ),
        pytest.param(
            f"""
{_HA_IMPORTS}
raise HomeAssistantError(
    translation_domain=DOMAIN,
)
""",
            id="domain_without_key",
        ),
        pytest.param(
            f"""
{_HA_IMPORTS}
raise HomeAssistantError("Something failed", translation_domain=DOMAIN)
""",
            id="hardcoded_with_domain_no_key",
        ),
    ],
)
def test_translation_key_domain_mismatch_flagged(
    linter: UnittestLinter,
    translations_checker: ExceptionTranslationsChecker,
    tmp_path: Path,
    code: str,
) -> None:
    """Test that translation_key without domain or domain without key is flagged."""
    integration_dir = _make_integration(tmp_path)
    root_node = astroid.parse(
        code,
        "homeassistant.components.test_int.coordinator",
    )
    root_node.file = str(integration_dir / "coordinator.py")

    walker = ASTWalker(linter)
    walker.add_checker(translations_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert (
        messages[0].msg_id == "home-assistant-exception-translation-key-domain-mismatch"
    )


def test_message_with_translation_key_flagged(
    linter: UnittestLinter,
    translations_checker: ExceptionTranslationsChecker,
    tmp_path: Path,
) -> None:
    """Test that passing both a message and translation_key is flagged."""
    integration_dir = _make_integration(tmp_path)
    root_node = astroid.parse(
        f"""
{_HA_IMPORTS}
raise HomeAssistantError(
    "This should not be here",
    translation_domain=DOMAIN,
    translation_key="some_error",
)
""",
        "homeassistant.components.test_int.coordinator",
    )
    root_node.file = str(integration_dir / "coordinator.py")

    walker = ASTWalker(linter)
    walker.add_checker(translations_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-exception-message-with-translation"


def test_missing_translation_key_flagged(
    linter: UnittestLinter,
    translations_checker: ExceptionTranslationsChecker,
    tmp_path: Path,
) -> None:
    """Test that a missing translation key in strings.json is flagged."""
    integration_dir = _make_integration(
        tmp_path,
        exceptions={"existing_key": {"message": "This exists"}},
    )
    root_node = astroid.parse(
        f"""
{_HA_IMPORTS}
raise HomeAssistantError(
    translation_domain=DOMAIN,
    translation_key="nonexistent_key",
)
""",
        "homeassistant.components.test_int.coordinator",
    )
    root_node.file = str(integration_dir / "coordinator.py")

    walker = ASTWalker(linter)
    walker.add_checker(translations_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-exception-translation-key-missing"
    assert "nonexistent_key" in messages[0].args[0]


def test_existing_translation_key_ok(
    linter: UnittestLinter,
    translations_checker: ExceptionTranslationsChecker,
    tmp_path: Path,
) -> None:
    """Test that an existing translation key passes."""
    integration_dir = _make_integration(
        tmp_path,
        exceptions={"some_error": {"message": "An error occurred"}},
    )
    root_node = astroid.parse(
        f"""
{_HA_IMPORTS}
raise HomeAssistantError(
    translation_domain=DOMAIN,
    translation_key="some_error",
)
""",
        "homeassistant.components.test_int.coordinator",
    )
    root_node.file = str(integration_dir / "coordinator.py")

    walker = ASTWalker(linter)
    walker.add_checker(translations_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


def test_extra_placeholders_flagged(
    linter: UnittestLinter,
    translations_checker: ExceptionTranslationsChecker,
    tmp_path: Path,
) -> None:
    """Test that extra placeholders are flagged when strings.json expects none."""
    integration_dir = _make_integration(
        tmp_path,
        exceptions={
            "some_error": {"message": "Something failed"},
        },
    )
    root_node = astroid.parse(
        f"""
{_HA_IMPORTS}
raise HomeAssistantError(
    translation_domain=DOMAIN,
    translation_key="some_error",
    translation_placeholders={{"extra": "value"}},
)
""",
        "homeassistant.components.test_int.coordinator",
    )
    root_node.file = str(integration_dir / "coordinator.py")

    walker = ASTWalker(linter)
    walker.add_checker(translations_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-exception-placeholder-mismatch"


def test_placeholder_mismatch_flagged(
    linter: UnittestLinter,
    translations_checker: ExceptionTranslationsChecker,
    tmp_path: Path,
) -> None:
    """Test that placeholder mismatches are flagged."""
    integration_dir = _make_integration(
        tmp_path,
        exceptions={
            "some_error": {"message": "Error for {device_name}: {error}"},
        },
    )
    root_node = astroid.parse(
        f"""
{_HA_IMPORTS}
raise HomeAssistantError(
    translation_domain=DOMAIN,
    translation_key="some_error",
    translation_placeholders={{"device_name": name, "wrong_key": "value"}},
)
""",
        "homeassistant.components.test_int.coordinator",
    )
    root_node.file = str(integration_dir / "coordinator.py")

    walker = ASTWalker(linter)
    walker.add_checker(translations_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-exception-placeholder-mismatch"


def test_placeholder_match_ok(
    linter: UnittestLinter,
    translations_checker: ExceptionTranslationsChecker,
    tmp_path: Path,
) -> None:
    """Test that matching placeholders pass."""
    integration_dir = _make_integration(
        tmp_path,
        exceptions={
            "some_error": {"message": "Error for {device_name}: {error}"},
        },
    )
    root_node = astroid.parse(
        f"""
{_HA_IMPORTS}
raise HomeAssistantError(
    translation_domain=DOMAIN,
    translation_key="some_error",
    translation_placeholders={{"device_name": name, "error": str(err)}},
)
""",
        "homeassistant.components.test_int.coordinator",
    )
    root_node.file = str(integration_dir / "coordinator.py")

    walker = ASTWalker(linter)
    walker.add_checker(translations_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


def test_placeholder_variable_resolved(
    linter: UnittestLinter,
    translations_checker: ExceptionTranslationsChecker,
    tmp_path: Path,
) -> None:
    """Test that placeholders via a variable are resolved through inference."""
    integration_dir = _make_integration(
        tmp_path,
        exceptions={
            "some_error": {"message": "Error for {device_name}: {error}"},
        },
    )
    root_node = astroid.parse(
        f"""
{_HA_IMPORTS}
placeholders = {{"device_name": name, "error": str(err)}}
raise HomeAssistantError(
    translation_domain=DOMAIN,
    translation_key="some_error",
    translation_placeholders=placeholders,
)
""",
        "homeassistant.components.test_int.coordinator",
    )
    root_node.file = str(integration_dir / "coordinator.py")

    walker = ASTWalker(linter)
    walker.add_checker(translations_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


def test_placeholder_variable_mismatch_flagged(
    linter: UnittestLinter,
    translations_checker: ExceptionTranslationsChecker,
    tmp_path: Path,
) -> None:
    """Test that a variable with wrong placeholder keys is still flagged."""
    integration_dir = _make_integration(
        tmp_path,
        exceptions={
            "some_error": {"message": "Error for {device_name}: {error}"},
        },
    )
    root_node = astroid.parse(
        f"""
{_HA_IMPORTS}
placeholders = {{"wrong": name}}
raise HomeAssistantError(
    translation_domain=DOMAIN,
    translation_key="some_error",
    translation_placeholders=placeholders,
)
""",
        "homeassistant.components.test_int.coordinator",
    )
    root_node.file = str(integration_dir / "coordinator.py")

    walker = ASTWalker(linter)
    walker.add_checker(translations_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-exception-placeholder-mismatch"


def test_dict_unpacking_placeholders_ok(
    linter: UnittestLinter,
    translations_checker: ExceptionTranslationsChecker,
    tmp_path: Path,
) -> None:
    """Test that **dict unpacking is resolved for placeholder validation."""
    integration_dir = _make_integration(
        tmp_path,
        exceptions={
            "some_error": {"message": "Error for {name}: {reason}"},
        },
    )
    root_node = astroid.parse(
        f"""
{_HA_IMPORTS}
base = {{"name": device_name}}
raise HomeAssistantError(
    translation_domain=DOMAIN,
    translation_key="some_error",
    translation_placeholders={{**base, "reason": str(err)}},
)
""",
        "homeassistant.components.test_int.coordinator",
    )
    root_node.file = str(integration_dir / "coordinator.py")

    walker = ASTWalker(linter)
    walker.add_checker(translations_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


def test_constant_placeholder_keys_ok(
    linter: UnittestLinter,
    translations_checker: ExceptionTranslationsChecker,
    tmp_path: Path,
) -> None:
    """Test that constant keys in placeholder dicts are resolved."""
    integration_dir = _make_integration(
        tmp_path,
        exceptions={
            "some_error": {"message": "Error for {name}"},
        },
    )
    root_node = astroid.parse(
        f"""
{_HA_IMPORTS}
ATTR_NAME = "name"
raise HomeAssistantError(
    translation_domain=DOMAIN,
    translation_key="some_error",
    translation_placeholders={{ATTR_NAME: device_name}},
)
""",
        "homeassistant.components.test_int.coordinator",
    )
    root_node.file = str(integration_dir / "coordinator.py")

    walker = ASTWalker(linter)
    walker.add_checker(translations_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


def test_key_reference_resolution(
    linter: UnittestLinter,
    translations_checker: ExceptionTranslationsChecker,
    tmp_path: Path,
) -> None:
    """Test that [%key:component::...%] references are resolved for placeholders."""
    # Create the referenced integration
    ref_dir = tmp_path / "homeassistant" / "components" / "other_int"
    ref_dir.mkdir(parents=True)
    (ref_dir / "strings.json").write_text(
        json.dumps({"exceptions": {"ref_error": {"message": "Error for {device}"}}})
    )

    # Create the integration that references it
    integration_dir = _make_integration(
        tmp_path,
        exceptions={
            "some_error": {
                "message": "[%key:component::other_int::exceptions::ref_error::message%]"
            },
        },
    )
    root_node = astroid.parse(
        f"""
{_HA_IMPORTS}
raise HomeAssistantError(
    translation_domain=DOMAIN,
    translation_key="some_error",
    translation_placeholders={{"device": device_name}},
)
""",
        "homeassistant.components.test_int.coordinator",
    )
    root_node.file = str(integration_dir / "coordinator.py")

    walker = ASTWalker(linter)
    walker.add_checker(translations_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)


def test_no_strings_json_flags_missing_key(
    linter: UnittestLinter,
    translations_checker: ExceptionTranslationsChecker,
    tmp_path: Path,
) -> None:
    """Test that a translation_key is flagged when no strings.json exists."""
    integration_dir = _make_integration(tmp_path)
    root_node = astroid.parse(
        f"""
{_HA_IMPORTS}
raise HomeAssistantError(
    translation_domain=DOMAIN,
    translation_key="some_error",
)
""",
        "homeassistant.components.test_int.coordinator",
    )
    root_node.file = str(integration_dir / "coordinator.py")

    walker = ASTWalker(linter)
    walker.add_checker(translations_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-exception-translation-key-missing"


def test_missing_placeholders_flagged(
    linter: UnittestLinter,
    translations_checker: ExceptionTranslationsChecker,
    tmp_path: Path,
) -> None:
    """Test that missing translation_placeholders are flagged when strings.json expects them."""
    integration_dir = _make_integration(
        tmp_path,
        exceptions={
            "some_error": {"message": "Error for {device_name}: {error}"},
        },
    )
    root_node = astroid.parse(
        f"""
{_HA_IMPORTS}
raise HomeAssistantError(
    translation_domain=DOMAIN,
    translation_key="some_error",
)
""",
        "homeassistant.components.test_int.coordinator",
    )
    root_node.file = str(integration_dir / "coordinator.py")

    walker = ASTWalker(linter)
    walker.add_checker(translations_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-exception-placeholder-mismatch"


def test_custom_integration_en_json(
    linter: UnittestLinter,
    translations_checker: ExceptionTranslationsChecker,
    tmp_path: Path,
) -> None:
    """Test that custom integrations use translations/en.json."""
    integration_dir = tmp_path / "homeassistant" / "components" / "test_int"
    integration_dir.mkdir(parents=True)
    translations_dir = integration_dir / "translations"
    translations_dir.mkdir()
    (translations_dir / "en.json").write_text(
        json.dumps({"exceptions": {"my_error": {"message": "It broke"}}})
    )

    root_node = astroid.parse(
        f"""
{_HA_IMPORTS}
raise HomeAssistantError(
    translation_domain=DOMAIN,
    translation_key="missing_key",
)
""",
        "homeassistant.components.test_int.coordinator",
    )
    root_node.file = str(integration_dir / "coordinator.py")

    walker = ASTWalker(linter)
    walker.add_checker(translations_checker)
    walker.walk(root_node)

    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-exception-translation-key-missing"


def test_not_integration_ignored(
    linter: UnittestLinter,
    translations_checker: ExceptionTranslationsChecker,
) -> None:
    """Test that non-integration modules are ignored."""
    root_node = astroid.parse(
        f'{_HA_IMPORTS}\nraise HomeAssistantError("hardcoded")',
        "tests.components.test_integration",
    )
    walker = ASTWalker(linter)
    walker.add_checker(translations_checker)

    with assert_no_messages(linter):
        walker.walk(root_node)
