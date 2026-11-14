"""Gather info for scaffolding."""

import json

from hassfest.model import IntegrationType

from homeassistant.util import slugify
from script.hassfest.icons import integration_category_keys
from script.hassfest.manifest import (
    CATEGORIES_DOCUMENTATION_URL,
    NO_CATEGORIES_INTEGRATION_TYPES,
    SUPPORTED_IOT_CLASSES,
)

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
                    "prompt": (
                        """What is the domain?

Hint: The domain is a short name consisting of characters and underscores.
This domain has to be unique, cannot be changed,
and has to match the directory name of the integration."""
                    ),
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
                "iot_class": "local_polling",
                "categories": ["diy_makers"],
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
            "validators": [CHECK_EMPTY],
            "converter": (
                lambda value: value if value.startswith("@") else f"@{value}"
            ),
        },
        "requirement": {
            "prompt": (
                "What PyPI package and version do you depend on? Leave blank for none."
            ),
            "validators": [
                [
                    "Versions should be pinned using '=='.",
                    lambda value: not value or "==" in value,
                ]
            ],
        },
        "iot_class": {
            "prompt": (
                f"""How will your integration gather data?

Valid values are {", ".join(SUPPORTED_IOT_CLASSES)}

More info @ https://contributors.home-assistant.io/core/integrations/manifest/#iot_class
"""
            ),
            "validators": [
                [
                    f"You need to pick one of {', '.join(SUPPORTED_IOT_CLASSES)}",
                    lambda value: value in SUPPORTED_IOT_CLASSES,
                ]
            ],
        },
    }

    if determine_auth:
        fields.update(
            {
                "authentication": {
                    "prompt": (
                        "Does Home Assistant need the user"
                        " to authenticate to control the"
                        " device/service? (yes/no)"
                    ),
                    "default": "yes",
                    **YES_NO,
                },
                "discoverable": {
                    "prompt": (
                        "Is the device/service discoverable"
                        " on the local network? (yes/no)"
                    ),
                    "default": "no",
                    **YES_NO,
                },
                "integration_type": {
                    "prompt": (
                        "What is the integration type?"
                        "\n\nValid types are "
                        f"{', '.join(IntegrationType)}."
                        "\nThis field is recommended and"
                        " required in some cases."
                        " To intentionally leave it"
                        " unset, type 'omit'."
                        "\n\nMore info @ "
                        "https://contributors.home-assistant.io"
                        "/core/integrations/manifest"
                        "/#integration_type\n"
                    ),
                    "validators": [
                        [
                            "You need to pick one of"
                            f" {', '.join(IntegrationType)}"
                            " or 'omit'.",
                            lambda value: value in IntegrationType or value == "omit",
                        ]
                    ],
                    "converter": lambda value: None if value == "omit" else value,
                },
                "oauth2": {
                    "prompt": (
                        "Can the user authenticate the device using OAuth2? (yes/no)"
                    ),
                    "default": "no",
                    **YES_NO,
                },
            }
        )

    info = _gather_info(fields)

    if info.get("integration_type") not in (
        NO_CATEGORIES_INTEGRATION_TYPES | {IntegrationType.VIRTUAL}
    ):
        info.update(_gather_categories())

    return info


def _split_categories(value: str) -> list[str]:
    """Split a comma separated list of categories."""
    return [category.strip() for category in value.split(",") if category.strip()]


def _gather_categories() -> dict:
    """Gather the categories of a new integration from user."""
    strings = json.loads((COMPONENT_DIR / "homeassistant" / "strings.json").read_text())
    known_categories = integration_category_keys(strings["integration_category"])

    return _gather_info(
        {
            "categories": {
                "prompt": (
                    f"""Which categories does your integration belong to?

Separate multiple categories with a comma.
Valid values are {", ".join(sorted(known_categories))}

More info @ {CATEGORIES_DOCUMENTATION_URL}
"""
                ),
                "validators": [
                    [
                        "You need to pick at least one category.",
                        _split_categories,
                    ],
                    [
                        "You need to pick from the valid values.",
                        lambda value: known_categories.issuperset(
                            _split_categories(value)
                        ),
                    ],
                    [
                        "You need to pick at most three categories.",
                        lambda value: len(_split_categories(value)) <= 3,
                    ],
                    [
                        "You need to pick each category only once.",
                        lambda value: (
                            len(set(_split_categories(value)))
                            == len(_split_categories(value))
                        ),
                    ],
                    [
                        "A subcategory implies its category, remove the category.",
                        lambda value: (
                            not any(
                                category.partition(".")[0] in _split_categories(value)
                                for category in _split_categories(value)
                                if "." in category
                            )
                        ),
                    ],
                ],
                "converter": _split_categories,
            }
        }
    )


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
            except (KeyboardInterrupt, EOFError) as err:
                raise ExitApp("Interrupted!", 1) from err

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
