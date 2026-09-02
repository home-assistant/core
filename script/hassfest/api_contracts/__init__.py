"""Generate and validate Home Assistant API contracts."""

from __future__ import annotations

import json
from pathlib import Path

from script.hassfest.model import Brand, Config, Integration

from .asyncapi import generate_websocket_asyncapi
from .common import IntegrationMetadata, SourceIndex
from .openapi import generate_rest_openapi

OPENAPI_PATH = Path("homeassistant/generated/rest_api_openapi.json")
ASYNCAPI_PATH = Path("homeassistant/generated/websocket_api_asyncapi.json")
CACHE_KEY = "api_contracts"


def _metadata(
    integrations: dict[str, Integration], config: Config
) -> dict[str, IntegrationMetadata]:
    """Build shared metadata from validated manifests and brands."""
    brands = Brand.load_dir(config.root / "homeassistant/brands", config)
    integration_brands = {
        domain: brand.name
        for brand in brands.values()
        for domain in brand.integrations
        if brand.name
    }
    return {
        domain: IntegrationMetadata(
            name=integration.name,
            documentation=integration.manifest.get(
                "documentation",
                f"https://www.home-assistant.io/integrations/{domain}/",
            ),
            group=integration.integration_type.value,
            brand=integration_brands.get(domain),
        )
        for domain, integration in integrations.items()
    }


def _documents(integrations: dict[str, Integration], config: Config) -> dict[Path, str]:
    """Render both contracts from one source index."""
    index = SourceIndex(config.root)
    metadata = _metadata(integrations, config)
    return {
        OPENAPI_PATH: json.dumps(
            generate_rest_openapi(index, metadata),
            indent=2,
            sort_keys=True,
        )
        + "\n",
        ASYNCAPI_PATH: json.dumps(
            generate_websocket_asyncapi(index, metadata),
            indent=2,
            sort_keys=True,
        )
        + "\n",
    }


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Validate committed API contracts."""
    config.cache[CACHE_KEY] = documents = _documents(integrations, config)
    for relative_path, content in documents.items():
        path = config.root / relative_path
        if not path.exists() or path.read_text() != content:
            config.add_error(
                "api_contracts",
                f"{relative_path} is not up to date. Run python3 -m script.hassfest",
                fixable=True,
            )


def generate(integrations: dict[str, Integration], config: Config) -> None:
    """Write API contracts prepared during validation."""
    documents: dict[Path, str] = config.cache[CACHE_KEY]
    for relative_path, content in documents.items():
        (config.root / relative_path).write_text(content)
