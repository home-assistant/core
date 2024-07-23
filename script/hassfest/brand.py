"""Brand validation."""

from __future__ import annotations

import voluptuous as vol
from voluptuous.humanize import humanize_error

from .model import Brand, Config, Integration

BRAND_SCHEMA = vol.Schema(
    {
        vol.Required("domain"): str,
        vol.Required("name"): str,
        vol.Optional("integrations"): [str],
        vol.Optional("iot_standards"): [
            vol.Any("homekit", "matter", "zigbee", "zwave")
        ],
    }
)


def _validate_brand(
    brand: Brand, integrations: dict[str, Integration], config: Config
) -> None:
    """Validate brand file."""
    try:
        BRAND_SCHEMA(brand.brand)
    except vol.Invalid as err:
        config.add_error(
            "brand",
            f"Invalid brand file {brand.path.name}: {humanize_error(brand.brand, err)}",
        )
        return

    if brand.domain != brand.path.stem:
        config.add_error(
            "brand",
            f"Domain '{brand.domain}' does not match file name {brand.path.name}",
        )

    if not brand.integrations and not brand.iot_standards:
        config.add_error(
            "brand",
            f"{brand.path.name}: At least one of integrations or "
            "iot_standards must be non-empty",
        )

    if brand.integrations:
        for sub_integration in brand.integrations:
            if sub_integration not in integrations:
                config.add_error(
                    "brand",
                    f"{brand.path.name}: References unknown integration {sub_integration}",
                )

    if brand.domain in integrations and (
        not brand.integrations or brand.domain not in brand.integrations
    ):
        config.add_error(
            "brand",
            f"{brand.path.name}: Brand '{brand.domain}' "
            f"is an integration but is missing in the brand's 'integrations' list'",
        )


def validate(
    brands: dict[str, Brand], integrations: dict[str, Integration], config: Config
) -> None:
    """Handle all integrations' brands."""
    for brand in brands.values():
        _validate_brand(brand, integrations, config)
