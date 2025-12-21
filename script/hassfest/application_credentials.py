"""Generate application_credentials data."""

from __future__ import annotations

from .model import Config, Integration
from .serializer import format_python_namespace


def generate_and_validate(integrations: dict[str, Integration], config: Config) -> str:
    """Validate and generate application_credentials data."""

    match_list = []

    for domain in sorted(integrations):
        integration = integrations[domain]
        application_credentials_file = integration.path / "application_credentials.py"
        if not application_credentials_file.is_file():
            continue

        match_list.append(domain)

    return format_python_namespace({"APPLICATION_CREDENTIALS": match_list})


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Validate application_credentials data."""
    application_credentials_path = (
        config.root / "homeassistant/generated/application_credentials.py"
    )
    config.cache["application_credentials"] = content = generate_and_validate(
        integrations, config
    )

    if config.specific_integrations:
        return

    if application_credentials_path.read_text(encoding="utf-8") != content:
        config.add_error(
            "application_credentials",
            "File application_credentials.py is not up to date. Run python3 -m script.hassfest",
            fixable=True,
        )


def generate(integrations: dict[str, Integration], config: Config) -> None:
    """Generate application_credentials data."""
    application_credentials_path = (
        config.root / "homeassistant/generated/application_credentials.py"
    )
    application_credentials_path.write_text(
        f"{config.cache['application_credentials']}", encoding="utf-8"
    )
