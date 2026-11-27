"""Validate integration code owners."""

from .model import Config, Integration, IntegrationType


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Validate GitHub handles in integration manifests."""
    for integration in integrations.values():
        if integration.integration_type == IntegrationType.VIRTUAL:
            continue
        codeowners = integration.manifest["codeowners"]
        if not codeowners:
            continue

        for owner in codeowners:
            if not owner.startswith("@"):
                integration.add_error(
                    "codeowners", "Code owners need to be valid GitHub handles."
                )
