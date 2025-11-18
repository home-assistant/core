"""Generate labs features file."""

from __future__ import annotations

from .model import Config, Integration
from .serializer import format_python_namespace


def generate_and_validate(integrations: dict[str, Integration]) -> str:
    """Validate and generate labs features data."""
    labs_dict: dict[str, list[str]] = {}

    for domain in sorted(integrations):
        integration = integrations[domain]
        labs_features = integration.manifest.get("labs_features")

        if not labs_features:
            continue

        if not isinstance(labs_features, dict):
            integration.add_error(
                "labs",
                f"labs_features must be a dict, got {type(labs_features).__name__}",
            )
            continue

        # Extract feature IDs from the dict
        feature_ids = []
        for feature_id, feature_config in labs_features.items():
            if not isinstance(feature_id, str):
                integration.add_error(
                    "labs",
                    f"labs_features keys must be strings, got {type(feature_id).__name__}",
                )
                break
            if not isinstance(feature_config, dict):
                integration.add_error(
                    "labs",
                    f"labs_features[{feature_id}] must be a dict, got {type(feature_config).__name__}",
                )
                break
            feature_ids.append(feature_id)
        else:
            # Only add if all features are valid
            if feature_ids:
                labs_dict[domain] = feature_ids

    return format_python_namespace(
        {
            "LABS_FEATURES": labs_dict,
        }
    )


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Validate labs features file."""
    labs_path = config.root / "homeassistant/generated/labs.py"
    config.cache["labs"] = content = generate_and_validate(integrations)

    if config.specific_integrations:
        return

    if not labs_path.exists() or labs_path.read_text() != content:
        config.add_error(
            "labs",
            "File labs.py is not up to date. Run python3 -m script.hassfest",
            fixable=True,
        )


def generate(integrations: dict[str, Integration], config: Config) -> None:
    """Generate labs features file."""
    labs_path = config.root / "homeassistant/generated/labs.py"
    labs_path.write_text(config.cache["labs"])
