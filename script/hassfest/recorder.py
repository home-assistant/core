"""Generate recorder file."""
from __future__ import annotations

from .model import Config, Integration
from .serializer import format_python_namespace


def generate_and_validate(integrations: dict[str, Integration]) -> str:
    """Validate and generate recorder data."""

    data: dict[str, set[str]] = {}

    for domain in sorted(integrations):
        exclude_list = integrations[domain].manifest.get("history_excluded_attributes")

        if not exclude_list:
            continue

        data[domain] = set(exclude_list)

    return format_python_namespace({"EXCLUDED_ATTRIBUTES": data})


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Validate recorder file."""
    recorder_path = config.root / "homeassistant/generated/recorder.py"
    config.cache["recorder"] = content = generate_and_validate(integrations)

    if config.specific_integrations:
        return

    with open(str(recorder_path)) as fp:
        if fp.read() != content:
            config.add_error(
                "mqtt",
                "File recorder.py is not up to date. Run python3 -m script.hassfest",
                fixable=True,
            )


def generate(integrations: dict[str, Integration], config: Config) -> None:
    """Generate recorder file."""
    recorder_path = config.root / "homeassistant/generated/recorder.py"
    with open(str(recorder_path), "w") as fp:
        fp.write(f"{config.cache['recorder']}")
