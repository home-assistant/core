"""Generate ssdp file."""
from __future__ import annotations

from collections import defaultdict

from .model import Config, Integration
from .serializer import format_python_namespace


def generate_and_validate(integrations: dict[str, Integration]) -> str:
    """Validate and generate ssdp data."""

    data = defaultdict(list)

    for domain in sorted(integrations):
        ssdp = integrations[domain].manifest.get("ssdp")

        if not ssdp:
            continue

        for matcher in ssdp:
            data[domain].append(matcher)

    return format_python_namespace({"SSDP": data})


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Validate ssdp file."""
    ssdp_path = config.root / "homeassistant/generated/ssdp.py"
    config.cache["ssdp"] = content = generate_and_validate(integrations)

    if config.specific_integrations:
        return

    with open(str(ssdp_path)) as fp:
        if fp.read() != content:
            config.add_error(
                "ssdp",
                "File ssdp.py is not up to date. Run python3 -m script.hassfest",
                fixable=True,
            )


def generate(integrations: dict[str, Integration], config: Config) -> None:
    """Generate ssdp file."""
    ssdp_path = config.root / "homeassistant/generated/ssdp.py"
    with open(str(ssdp_path), "w") as fp:
        fp.write(f"{config.cache['ssdp']}")
