"""Validate coverage files."""
from typing import Dict

from .model import Config, Integration


def validate(integrations: Dict[str, Integration], config: Config):
    """Validate coverage."""
    codeowners_path = config.root / ".coveragerc"

    referenced = set()

    with codeowners_path.open("rt") as fp:
        for line in fp:
            line = line.strip()

            if not line.startswith("homeassistant/components/"):
                continue

            referenced.add(line.split("/")[2])

    for domain in integrations:
        referenced.discard(domain)

    if referenced:
        raise RuntimeError(
            f".coveragerc references invalid integrations: {', '.join(referenced)}"
        )
