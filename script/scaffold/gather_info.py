"""Gather info for scaffolding."""
from homeassistant.util import slugify

from .const import COMPONENT_DIR
from .model import Info
from .error import ExitApp


CHECK_EMPTY = ["Cannot be empty", lambda value: value]


FIELDS = {
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
            ["Versions should be pinned using '=='.", lambda value: "==" in value]
        ],
    },
}


def gather_info() -> Info:
    """Gather info from user."""
    answers = {}

    for key, info in FIELDS.items():
        hint = None
        while key not in answers:
            if hint is not None:
                print()
                print(f"Error: {hint}")

            try:
                print()
                value = input(info["prompt"] + "\n> ")
            except (KeyboardInterrupt, EOFError):
                raise ExitApp("Interrupted!", 1)

            value = value.strip()
            hint = None

            for validator_hint, validator in info["validators"]:
                if not validator(value):
                    hint = validator_hint
                    break

            if hint is None:
                answers[key] = value

    print()
    return Info(**answers)
