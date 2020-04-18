"""Gather info for scaffolding."""
import json

from homeassistant.util import slugify

from .const import COMPONENT_DIR
from .error import ExitApp
from .model import Info

CHECK_EMPTY = ["Cannot be empty", lambda value: value]


def gather_info(arguments) -> Info:
    """Gather info."""
    if arguments.integration:
        info = {"domain": arguments.integration}
    elif arguments.develop:
        print("Running in developer mode. Automatically filling in info.")
        print()
        info = {"domain": "develop"}
    else:
        info = _gather_info(
            {
                "domain": {
                    "prompt": "What is the domain?",
                    "validators": [
                        CHECK_EMPTY,
                        [
                            "Domains cannot contain spaces or special characters.",
                            lambda value: value == slugify(value),
                        ],
                    ],
                }
            }
        )

    info["is_new"] = not (COMPONENT_DIR / info["domain"] / "manifest.json").exists()

    if not info["is_new"]:
        return _load_existing_integration(info["domain"])

    if arguments.develop:
        info.update(
            {
                "name": "Develop Hub",
                "codeowner": "@developer",
                "requirement": "aiodevelop==1.2.3",
                "oauth2": True,
            }
        )
    else:
        info.update(gather_new_integration(arguments.template == "integration"))

    return Info(**info)


YES_NO = {
    "validators": [["Type either 'yes' or 'no'", lambda value: value in ("yes", "no")]],
    "converter": lambda value: value == "yes",
}


def gather_new_integration(determine_auth: bool) -> Info:
    """Gather info about new integration from user."""
    fields = {
        "name": {
            "prompt": "What is the name of your integration?",
            "validators": [CHECK_EMPTY],
        },
        "codeowner": {
            "prompt": "What is your GitHub handle?",
            "validators": [
                CHECK_EMPTY,
                [
                    'GitHub handles need to start with an "@"',
                    lambda value: value.startswith("@"),
                ],
            ],
        },
        "requirement": {
            "prompt": "What PyPI package and version do you depend on? Leave blank for none.",
            "validators": [
                [
                    "Versions should be pinned using '=='.",
                    lambda value: not value or "==" in value,
                ]
            ],
        },
    }

    if determine_auth:
        fields.update(
            {
                "authentication": {
                    "prompt": "Does Home Assistant need the user to authenticate to control the device/service? (yes/no)",
                    "default": "yes",
                    **YES_NO,
                },
                "discoverable": {
                    "prompt": "Is the device/service discoverable on the local network? (yes/no)",
                    "default": "no",
                    **YES_NO,
                },
                "oauth2": {
                    "prompt": "Can the user authenticate the device using OAuth2? (yes/no)",
                    "default": "no",
                    **YES_NO,
                },
            }
        )

    return _gather_info(fields)


def _load_existing_integration(domain) -> Info:
    """Load an existing integration."""
    if not (COMPONENT_DIR / domain).exists():
        raise ExitApp("Integration does not exist", 1)

    manifest = json.loads((COMPONENT_DIR / domain / "manifest.json").read_text())

    return Info(domain=domain, name=manifest["name"], is_new=False)


def _gather_info(fields) -> dict:
    """Gather info from user."""
    answers = {}

    for key, info in fields.items():
        hint = None
        while key not in answers:
            if hint is not None:
                print()
                print(f"Error: {hint}")

            try:
                print()
                msg = info["prompt"]
                if "default" in info:
                    msg += f" [{info['default']}]"
                value = input(f"{msg}\n> ")
            except (KeyboardInterrupt, EOFError):
                raise ExitApp("Interrupted!", 1)

            value = value.strip()

            if value == "" and "default" in info:
                value = info["default"]

            hint = None

            for validator_hint, validator in info["validators"]:
                if not validator(value):
                    hint = validator_hint
                    break

            if hint is None:
                if "converter" in info:
                    value = info["converter"](value)
                answers[key] = value

    return answers
