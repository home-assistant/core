"""Validate coverage files."""
from pathlib import Path
from typing import Dict

from .model import Config, Integration


def validate(integrations: Dict[str, Integration], config: Config):
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
            while "*" in path.name:
                path = path.parent

            if not path.exists():
                not_found.append(line)

    if not not_found:
        return

    errors = []

    if not_found:
        errors.append(
            f".coveragerc references files that don't exist: {', '.join(not_found)}."
        )

    raise RuntimeError(" ".join(errors))
