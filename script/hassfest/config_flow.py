"""Generate config flow file."""

from __future__ import annotations

import json
from typing import Any

from .brand import validate as validate_brands
from .model import Brand, Config, Integration
from .serializer import format_python_namespace

UNIQUE_ID_IGNORE = {"huawei_lte", "mqtt", "adguard"}


def _validate_integration(config: Config, integration: Integration) -> None:
    """Validate config flow of an integration."""
    config_flow_file = integration.path / "config_flow.py"

    if not config_flow_file.is_file():
        if integration.manifest.get("config_flow"):
            integration.add_error(
                "config_flow",
                "Config flows need to be defined in the file config_flow.py",
            )
        return

    config_flow = config_flow_file.read_text()

    needs_unique_id = integration.domain not in UNIQUE_ID_IGNORE and (
        "async_step_discovery" in config_flow
        or "async_step_bluetooth" in config_flow
        or "async_step_hassio" in config_flow
        or "async_step_homekit" in config_flow
        or "async_step_mqtt" in config_flow
        or "async_step_ssdp" in config_flow
        or "async_step_zeroconf" in config_flow
        or "async_step_dhcp" in config_flow
        or "async_step_usb" in config_flow
    )

    if not needs_unique_id:
        return

    has_unique_id = (
        "self.async_set_unique_id" in config_flow
        or "self._async_handle_discovery_without_unique_id" in config_flow
        or "register_discovery_flow" in config_flow
        or "AbstractOAuth2FlowHandler" in config_flow
    )

    if has_unique_id:
        return

    if config.specific_integrations:
        notice_method = integration.add_warning
    else:
        notice_method = integration.add_error

    notice_method(
        "config_flow", "Config flows that are discoverable need to set a unique ID"
    )


def _generate_and_validate(integrations: dict[str, Integration], config: Config) -> str:
    """Validate and generate config flow data."""
    domains: dict[str, list[str]] = {
        "integration": [],
        "helper": [],
    }

    for domain in sorted(integrations):
        integration = integrations[domain]
        if not integration.config_flow:
            continue

        _validate_integration(config, integration)

        if integration.integration_type == "helper":
            domains["helper"].append(domain)
        else:
            domains["integration"].append(domain)

    return format_python_namespace({"FLOWS": domains})


def _populate_brand_integrations(
    integration_data: dict[str, Any],
    integrations: dict[str, Integration],
    brand_metadata: dict[str, Any],
    sub_integrations: list[str],
) -> None:
    """Add referenced integrations to a brand's metadata."""
    brand_metadata.setdefault("integrations", {})
    for domain in sub_integrations:
        integration = integrations.get(domain)
        if not integration or integration.integration_type in (
            "entity",
            "hardware",
            "system",
        ):
            continue
        metadata: dict[str, Any] = {
            "integration_type": integration.integration_type,
        }
        # Always set the config_flow key to avoid breaking the frontend
        # https://github.com/home-assistant/frontend/issues/14376
        metadata["config_flow"] = bool(integration.config_flow)
        if integration.iot_class:
            metadata["iot_class"] = integration.iot_class
        if integration.supported_by:
            metadata["supported_by"] = integration.supported_by
        if integration.iot_standards:
            metadata["iot_standards"] = integration.iot_standards
        if integration.translated_name:
            integration_data["translated_name"].add(domain)
        else:
            metadata["name"] = integration.name
        brand_metadata["integrations"][domain] = metadata


def _generate_integrations(
    brands: dict[str, Brand],
    integrations: dict[str, Integration],
    config: Config,
) -> str:
    """Generate integrations data."""

    result: dict[str, Any] = {
        "integration": {},
        "helper": {},
        "translated_name": set(),
    }

    # Not all integrations will have an item in the brands collection.
    # The config flow data index will be the union of the integrations without a brands item
    # and the brand domain names from the brands collection.

    # Compile a set of integrations which are referenced from at least one brand's
    # integrations list. These integrations will not be present in the root level of the
    # generated config flow index.
    brand_integration_domains = {
        brand_integration_domain
        for brand in brands.values()
        for brand_integration_domain in brand.integrations or []
    }

    # Compile a set of integrations which are not referenced from any brand's
    # integrations list.
    primary_domains = {
        domain
        for domain, integration in integrations.items()
        if domain not in brand_integration_domains
    }
    # Add all brands to the set
    primary_domains |= set(brands)

    # Generate the config flow index
    for domain in sorted(primary_domains):
        metadata: dict[str, Any] = {}

        if brand := brands.get(domain):
            metadata["name"] = brand.name
            if brand.integrations:
                # Add the integrations which are referenced from the brand's
                # integrations list
                _populate_brand_integrations(
                    result, integrations, metadata, brand.integrations
                )
            if brand.iot_standards:
                metadata["iot_standards"] = brand.iot_standards
            result["integration"][domain] = metadata
        else:  # integration
            integration = integrations[domain]
            if integration.integration_type in ("entity", "system", "hardware"):
                continue

            if integration.translated_name:
                result["translated_name"].add(domain)
            else:
                metadata["name"] = integration.name

            metadata["integration_type"] = integration.integration_type

            if integration.integration_type == "virtual":
                if integration.supported_by:
                    metadata["supported_by"] = integration.supported_by
                if integration.iot_standards:
                    metadata["iot_standards"] = integration.iot_standards
            else:
                metadata["config_flow"] = integration.config_flow
                if integration.iot_class:
                    metadata["iot_class"] = integration.iot_class

                if single_config_entry := integration.manifest.get(
                    "single_config_entry"
                ):
                    metadata["single_config_entry"] = single_config_entry

            if integration.integration_type == "helper":
                result["helper"][domain] = metadata
            else:
                result["integration"][domain] = metadata

    return json.dumps(
        result | {"translated_name": sorted(result["translated_name"])}, indent=2
    )


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Validate config flow file."""
    config_flow_path = config.root / "homeassistant/generated/config_flows.py"
    integrations_path = config.root / "homeassistant/generated/integrations.json"
    config.cache["config_flow"] = content = _generate_and_validate(integrations, config)

    if config.specific_integrations:
        return

    brands = Brand.load_dir(config.root / "homeassistant/brands", config)
    validate_brands(brands, integrations, config)

    if config_flow_path.read_text() != content:
        config.add_error(
            "config_flow",
            "File config_flows.py is not up to date. Run python3 -m script.hassfest",
            fixable=True,
        )

    config.cache["integrations"] = content = _generate_integrations(
        brands, integrations, config
    )
    if integrations_path.read_text() != content + "\n":
        config.add_error(
            "config_flow",
            "File integrations.json is not up to date. "
            "Run python3 -m script.hassfest",
            fixable=True,
        )


def generate(integrations: dict[str, Integration], config: Config) -> None:
    """Generate config flow file."""
    config_flow_path = config.root / "homeassistant/generated/config_flows.py"
    integrations_path = config.root / "homeassistant/generated/integrations.json"
    config_flow_path.write_text(f"{config.cache['config_flow']}")
    integrations_path.write_text(f"{config.cache['integrations']}\n")
