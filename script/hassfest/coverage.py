"""Validate coverage files."""
from __future__ import annotations

from pathlib import Path

from .model import Config, Integration

DONT_IGNORE = (
    "config_flow.py",
    "device_action.py",
    "device_condition.py",
    "device_trigger.py",
    "diagnostics.py",
    "group.py",
    "intent.py",
    "logbook.py",
    "media_source.py",
    "recorder.py",
    "scene.py",
)


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Validate coverage."""
    coverage_path = config.root / ".coveragerc"

    not_found: list[str] = []
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

            if not line.startswith("homeassistant/components/") or len(path.parts) != 4:
                continue

            integration_path = path.parent

            integration = integrations[integration_path.name]

            if (
                path.parts[-1] == "*"
                and Path(f"tests/components/{integration.domain}/__init__.py").exists()
            ):
                integration.add_error(
                    "coverage",
                    "has tests and should not use wildcard in .coveragerc file",
                )

            for check in DONT_IGNORE:
                if path.parts[-1] not in {"*", check}:
                    continue

                if (integration_path / check).exists():
                    integration.add_error(
                        "coverage",
                        f"{check} must not be ignored by the .coveragerc file",
                    )

    if not_found:
        raise RuntimeError(
            f".coveragerc references files that don't exist: {', '.join(not_found)}."
        )
