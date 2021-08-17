"""Generate an integration."""
from pathlib import Path

from .model import Info

TEMPLATE_DIR = Path(__file__).parent / "templates"
TEMPLATE_INTEGRATION = TEMPLATE_DIR / "integration"
TEMPLATE_TESTS = TEMPLATE_DIR / "tests"


def generate(template: str, info: Info) -> None:
    """Generate a template."""
    print(f"Scaffolding {template} for the {info.domain} integration...")
    _ensure_tests_dir_exists(info)
    _generate(TEMPLATE_DIR / template / "integration", info.integration_dir, info)
    _generate(TEMPLATE_DIR / template / "tests", info.tests_dir, info)
    _custom_tasks(template, info)
    print()


def _generate(src_dir, target_dir, info: Info) -> None:
    """Generate an integration."""
    replaces = {"NEW_DOMAIN": info.domain, "NEW_NAME": info.name}

    if not target_dir.exists():
        target_dir.mkdir()

    for source_file in src_dir.glob("**/*"):
        content = source_file.read_text()

        for to_search, to_replace in replaces.items():
            content = content.replace(to_search, to_replace)

        target_file = target_dir / source_file.relative_to(src_dir)

        # If the target file exists, create our template as EXAMPLE_<filename>.
        # Exception: If we are creating a new integration, we can end up running integration base
        # and a config flows on top of one another. In that case, we want to override the files.
        if not info.is_new and target_file.exists():
            new_name = f"EXAMPLE_{target_file.name}"
            print(f"File {target_file} already exists, creating {new_name} instead.")
            target_file = target_file.parent / new_name
            info.examples_added.add(target_file)
        elif src_dir.name == "integration":
            info.files_added.add(target_file)
        else:
            info.tests_added.add(target_file)

        print(f"Writing {target_file}")
        target_file.write_text(content)


def _ensure_tests_dir_exists(info: Info) -> None:
    """Ensure a test dir exists."""
    if info.tests_dir.exists():
        return

    info.tests_dir.mkdir()
    print(f"Writing {info.tests_dir / '__init__.py'}")
    (info.tests_dir / "__init__.py").write_text(
        f'"""Tests for the {info.name} integration."""\n'
    )


def _append(path: Path, text):
    """Append some text to a path."""
    path.write_text(path.read_text() + text)


def _custom_tasks(template, info: Info) -> None:
    """Handle custom tasks for templates."""
    if template == "integration":
        changes = {"codeowners": [info.codeowner], "iot_class": info.iot_class}

        if info.requirement:
            changes["requirements"] = [info.requirement]

        info.update_manifest(**changes)

    elif template == "device_trigger":
        info.update_strings(
            device_automation={
                **info.strings().get("device_automation", {}),
                "trigger_type": {
                    "turned_on": "{entity_name} turned on",
                    "turned_off": "{entity_name} turned off",
                },
            }
        )

    elif template == "device_condition":
        info.update_strings(
            device_automation={
                **info.strings().get("device_automation", {}),
                "condition_type": {
                    "is_on": "{entity_name} is on",
                    "is_off": "{entity_name} is off",
                },
            }
        )

    elif template == "device_action":
        info.update_strings(
            device_automation={
                **info.strings().get("device_automation", {}),
                "action_type": {
                    "turn_on": "Turn on {entity_name}",
                    "turn_off": "Turn off {entity_name}",
                },
            }
        )

    elif template == "config_flow":
        info.update_manifest(config_flow=True)
        info.update_strings(
            config={
                "step": {
                    "user": {
                        "data": {
                            "host": "[%key:common::config_flow::data::host%]",
                            "username": "[%key:common::config_flow::data::username%]",
                            "password": "[%key:common::config_flow::data::password%]",
                        },
                    }
                },
                "error": {
                    "cannot_connect": "[%key:common::config_flow::error::cannot_connect%]",
                    "invalid_auth": "[%key:common::config_flow::error::invalid_auth%]",
                    "unknown": "[%key:common::config_flow::error::unknown%]",
                },
                "abort": {
                    "already_configured": "[%key:common::config_flow::abort::already_configured_device%]"
                },
            },
        )

    elif template == "config_flow_discovery":
        info.update_manifest(config_flow=True)
        info.update_strings(
            config={
                "step": {
                    "confirm": {
                        "description": "[%key:common::config_flow::description::confirm_setup%]",
                    }
                },
                "abort": {
                    "single_instance_allowed": "[%key:common::config_flow::abort::single_instance_allowed%]",
                    "no_devices_found": "[%key:common::config_flow::abort::no_devices_found%]",
                },
            },
        )

    elif template == "config_flow_oauth2":
        info.update_manifest(config_flow=True, dependencies=["http"])
        info.update_strings(
            config={
                "step": {
                    "pick_implementation": {
                        "title": "[%key:common::config_flow::title::oauth2_pick_implementation%]"
                    }
                },
                "abort": {
                    "already_configured": "[%key:common::config_flow::abort::already_configured_account%]",
                    "already_in_progress": "[%key:common::config_flow::abort::already_in_progress%]",
                    "oauth_error": "[%key:common::config_flow::abort::oauth2_error%]",
                    "missing_configuration": "[%key:common::config_flow::abort::oauth2_missing_configuration%]",
                    "authorize_url_timeout": "[%key:common::config_flow::abort::oauth2_authorize_url_timeout%]",
                    "no_url_available": "[%key:common::config_flow::abort::oauth2_no_url_available%]",
                },
                "create_entry": {
                    "default": "[%key:common::config_flow::create_entry::authenticated%]"
                },
            },
        )
