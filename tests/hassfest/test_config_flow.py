"""Tests for hassfest config flow and integrations.json generation."""

import json
from pathlib import Path
from typing import Any

from script.hassfest import config_flow
from script.hassfest.model import Brand, Config, Integration


def _integration(config: Config, domain: str, **manifest: Any) -> Integration:
    """Return an integration with the given manifest keys."""
    return Integration(
        Path(domain),
        _config=config,
        _manifest={"domain": domain, "name": domain.title(), **manifest},
    )


def _generate(
    config: Config,
    integrations: list[Integration],
    brands: list[Brand] | None = None,
) -> dict[str, Any]:
    """Generate integrations.json and return its integration section."""
    generated = config_flow._generate_integrations(
        {brand.domain: brand for brand in brands or []},
        {integration.domain: integration for integration in integrations},
        config,
    )
    return json.loads(generated)["integration"]


def test_categories(config: Config) -> None:
    """Test categories are added, and left out when there are none."""
    generated = _generate(
        config,
        [
            _integration(
                config,
                "shelly",
                integration_type="device",
                categories=["plugs_switches", "energy.meters_monitoring"],
            ),
            _integration(config, "no_categories", integration_type="device"),
        ],
    )

    assert generated["shelly"]["categories"] == [
        "plugs_switches",
        "energy.meters_monitoring",
    ]
    assert "categories" not in generated["no_categories"]


def test_virtual_integration_inherits_categories(config: Config) -> None:
    """Test virtual integrations get the categories of their supported_by."""
    generated = _generate(
        config,
        [
            _integration(
                config,
                "motion_blinds",
                integration_type="hub",
                categories=["blinds_curtains"],
            ),
            _integration(
                config,
                "acomax",
                integration_type="virtual",
                supported_by="motion_blinds",
            ),
            _integration(
                config,
                "missing_target",
                integration_type="virtual",
                supported_by="does_not_exist",
            ),
        ],
    )

    assert generated["acomax"]["categories"] == ["blinds_curtains"]
    assert "categories" not in generated["missing_target"]


def test_brand_integrations_categories(config: Config) -> None:
    """Test integrations under a brand get categories, virtual ones inherited."""
    generated = _generate(
        config,
        [
            _integration(
                config,
                "motion_blinds",
                integration_type="hub",
                categories=["blinds_curtains"],
            ),
            _integration(
                config,
                "acomax",
                integration_type="virtual",
                supported_by="motion_blinds",
            ),
        ],
        [
            Brand(
                Path("blinds_brand"),
                _brand={
                    "domain": "blinds_brand",
                    "name": "Blinds brand",
                    "integrations": ["motion_blinds", "acomax"],
                },
            )
        ],
    )

    brand_integrations = generated["blinds_brand"]["integrations"]
    assert brand_integrations["motion_blinds"]["categories"] == ["blinds_curtains"]
    assert brand_integrations["acomax"]["categories"] == ["blinds_curtains"]


def test_connectivity(config: Config) -> None:
    """Test connectivity is added, and left out when there is none."""
    generated = _generate(
        config,
        [
            _integration(
                config,
                "zha",
                integration_type="hub",
                connectivity=["zigbee"],
            ),
            _integration(config, "no_connectivity", integration_type="device"),
        ],
    )

    assert generated["zha"]["connectivity"] == ["zigbee"]
    assert "connectivity" not in generated["no_connectivity"]


def test_virtual_integration_inherits_connectivity(config: Config) -> None:
    """Test virtual integrations get the connectivity of their supported_by."""
    generated = _generate(
        config,
        [
            _integration(
                config,
                "motion_blinds",
                integration_type="hub",
                connectivity=["network"],
            ),
            _integration(
                config,
                "acomax",
                integration_type="virtual",
                supported_by="motion_blinds",
            ),
            _integration(
                config,
                "missing_target",
                integration_type="virtual",
                supported_by="does_not_exist",
            ),
        ],
    )

    assert generated["acomax"]["connectivity"] == ["network"]
    assert "connectivity" not in generated["missing_target"]


def test_brand_integrations_connectivity(config: Config) -> None:
    """Test integrations under a brand get connectivity, virtual ones inherited."""
    generated = _generate(
        config,
        [
            _integration(
                config,
                "motion_blinds",
                integration_type="hub",
                connectivity=["network"],
            ),
            _integration(
                config,
                "acomax",
                integration_type="virtual",
                supported_by="motion_blinds",
            ),
        ],
        [
            Brand(
                Path("blinds_brand"),
                _brand={
                    "domain": "blinds_brand",
                    "name": "Blinds brand",
                    "integrations": ["motion_blinds", "acomax"],
                },
            )
        ],
    )

    brand_integrations = generated["blinds_brand"]["integrations"]
    assert brand_integrations["motion_blinds"]["connectivity"] == ["network"]
    assert brand_integrations["acomax"]["connectivity"] == ["network"]
