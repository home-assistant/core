"""Generate an integration."""
from pathlib import Path

from .error import ExitApp
from .model import Info

TEMPLATE_DIR = Path(__file__).parent / "templates"
TEMPLATE_INTEGRATION = TEMPLATE_DIR / "integration"
TEMPLATE_TESTS = TEMPLATE_DIR / "tests"


def generate(template: str, info: Info) -> None:
    """Generate a template."""
    _validate(template, info)

    print(f"Scaffolding {template} for the {info.domain} integration...")
    _ensure_tests_dir_exists(info)
    _generate(TEMPLATE_DIR / template / "integration", info.integration_dir, info)
    _generate(TEMPLATE_DIR / template / "tests", info.tests_dir, info)
    _custom_tasks(template, info)
    print()


def _validate(template, info):
    """Validate we can run this task."""
    if template == "config_flow":
        if (info.integration_dir / "config_flow.py").exists():
            raise ExitApp(f"Integration {info.domain} already has a config flow.")


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


def _custom_tasks(template, info) -> None:
    """Handle custom tasks for templates."""
    if template == "integration":
        changes = {"codeowners": [info.codeowner]}

        if info.requirement:
            changes["requirements"] = [info.requirement]

        info.update_manifest(**changes)

    if template == "device_trigger":
        info.update_strings(
            device_automation={
                **info.strings().get("device_automation", {}),
                "trigger_type": {
                    "turned_on": "{entity_name} turned on",
                    "turned_off": "{entity_name} turned off",
                },
            }
        )

    if template == "device_condition":
        info.update_strings(
            device_automation={
                **info.strings().get("device_automation", {}),
                "condtion_type": {
                    "is_on": "{entity_name} is on",
                    "is_off": "{entity_name} is off",
                },
            }
        )

    if template == "device_action":
        info.update_strings(
            device_automation={
                **info.strings().get("device_automation", {}),
                "action_type": {
                    "turn_on": "Turn on {entity_name}",
                    "turn_off": "Turn off {entity_name}",
                },
            }
        )

    if template == "config_flow":
        info.update_manifest(config_flow=True)
        info.update_strings(
            config={
                "title": info.name,
                "step": {
                    "user": {"title": "Connect to the device", "data": {"host": "Host"}}
                },
                "error": {
                    "cannot_connect": "Failed to connect, please try again",
                    "invalid_auth": "Invalid authentication",
                    "unknown": "Unexpected error",
                },
                "abort": {"already_configured": "Device is already configured"},
            }
        )

    if template == "config_flow_discovery":
        info.update_manifest(config_flow=True)
        info.update_strings(
            config={
                "title": info.name,
                "step": {
                    "confirm": {
                        "title": info.name,
                        "description": f"Do you want to set up {info.name}?",
                    }
                },
                "abort": {
                    "single_instance_allowed": f"Only a single configuration of {info.name} is possible.",
                    "no_devices_found": f"No {info.name} devices found on the network.",
                },
            }
        )

    if template in ("config_flow", "config_flow_discovery"):
        init_file = info.integration_dir / "__init__.py"
        init_file.write_text(
            init_file.read_text()
            + """

async def async_setup_entry(hass, entry):
    \"\"\"Set up a config entry for NEW_NAME.\"\"\"
    # TODO forward the entry for each platform that you want to set up.
    # hass.async_create_task(
    #     hass.config_entries.async_forward_entry_setup(entry, "media_player")
    # )

    return True
"""
        )
