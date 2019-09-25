"""Gather info for scaffolding."""
import json

from homeassistant.util import slugify

from .const import COMPONENT_DIR
from .model import Info
from .error import ExitApp


CHECK_EMPTY = ["Cannot be empty", lambda value: value]


def gather_info(arguments) -> Info:
    """Gather info."""
    existing = arguments.template != "integration"

    if arguments.develop:
        print("Running in developer mode. Automatically filling in info.")
        print()

    if existing:
        if arguments.develop:
            return _load_existing_integration("develop")

        if arguments.integration:
            return _load_existing_integration(arguments.integration)

        return gather_existing_integration()

    if arguments.develop:
        return Info(
            domain="develop",
            name="Develop Hub",
            codeowner="@developer",
            requirement="aiodevelop==1.2.3",
        )

    return gather_new_integration()


def gather_new_integration() -> Info:
    """Gather info about new integration from user."""
    return Info(
        **_gather_info(
            {
                "domain": {
                    "prompt": "What is the domain?",
                    "validators": [
                        CHECK_EMPTY,
                        [
                            "Domains cannot contain spaces or special characters.",
                            lambda value: value == slugify(value),
                        ],
                        [
                            "There already is an integration with this domain.",
                            lambda value: not (COMPONENT_DIR / value).exists(),
                        ],
                    ],
                },
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
                "authentication": {
                    "prompt": "Does Home Assistant need the user to authenticate to control the device/service? (yes/no)",
                    "default": "yes",
                    "validators": [
                        [
                            "Type either 'yes' or 'no'",
                            lambda value: value in ("yes", "no"),
                        ]
                    ],
                    "convertor": lambda value: value == "yes",
                },
                "discoverable": {
                    "prompt": "Is the device/service discoverable on the local network? (yes/no)",
                    "default": "no",
                    "validators": [
                        [
                            "Type either 'yes' or 'no'",
                            lambda value: value in ("yes", "no"),
                        ]
                    ],
                    "convertor": lambda value: value == "yes",
                },
            }
        )
    )


def gather_existing_integration() -> Info:
    """Gather info about existing integration from user."""
    answers = _gather_info(
        {
            "domain": {
                "prompt": "What is the domain?",
                "validators": [
                    CHECK_EMPTY,
                    [
                        "Domains cannot contain spaces or special characters.",
                        lambda value: value == slugify(value),
                    ],
                    [
                        "This integration does not exist.",
                        lambda value: (COMPONENT_DIR / value).exists(),
                    ],
                ],
            }
        }
    )

    return _load_existing_integration(answers["domain"])


def _load_existing_integration(domain) -> Info:
    """Load an existing integration."""
    if not (COMPONENT_DIR / domain).exists():
        raise ExitApp("Integration does not exist", 1)

    manifest = json.loads((COMPONENT_DIR / domain / "manifest.json").read_text())

    return Info(domain=domain, name=manifest["name"])


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
                if "convertor" in info:
                    value = info["convertor"](value)
                answers[key] = value

    print()
    return answers
