"""Validate coverage files."""
from __future__ import annotations

from pathlib import Path

from .model import Config, Integration

DONT_IGNORE = (
    "config_flow.py",
    "device_action.py",
    "device_condition.py",
    "device_trigger.py",
    "group.py",
    "intent.py",
    "logbook.py",
    "media_source.py",
    "scene.py",
)

# They were violating when we introduced this check
# Need to be fixed in a future PR.
ALLOWED_IGNORE_VIOLATIONS = {
    ("doorbird", "logbook.py"),
    ("elkm1", "scene.py"),
    ("fibaro", "scene.py"),
    ("lcn", "scene.py"),
    ("lutron", "scene.py"),
    ("tuya", "scene.py"),
    ("velux", "scene.py"),
}


def validate(integrations: dict[str, Integration], config: Config):
    """Validate coverage."""
    coverage_path = config.root / ".coveragerc"

    not_found = []
    checking = False

    with coverage_path.open("rt") as fp:
        for line in fp:
            line = line.strip()

            if not line or line.startswith("#"):
                continue

            if not checking:
                if line == "omit =":
                    checking = True
                continue

            # Finished
            if line == "[report]":
                break

            path = Path(line)

            # Discard wildcard
            path_exists = path
            while "*" in path_exists.name:
                path_exists = path_exists.parent

            if not path_exists.exists():
                not_found.append(line)
                continue

            if (
                not line.startswith("homeassistant/components/")
                or len(path.parts) != 4
                or path.parts[-1] != "*"
            ):
                continue

            integration_path = path.parent

            integration = integrations[integration_path.name]

            for check in DONT_IGNORE:
                if (integration_path.name, check) in ALLOWED_IGNORE_VIOLATIONS:
                    continue

                if (integration_path / check).exists():
                    integration.add_error(
                        "coverage",
                        f"{check} must not be ignored by the .coveragerc file",
                    )

    if not not_found:
        return

    errors = []

    if not_found:
        errors.append(
            f".coveragerc references files that don't exist: {', '.join(not_found)}."
        )

    raise RuntimeError(" ".join(errors))
