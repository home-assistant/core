"""Test component helpers."""

from collections import OrderedDict

from homeassistant import helpers


def test_extract_domain_configs() -> None:
    """Test the extraction of domain configuration."""
    config = {
        "zone": None,
        "zoner": None,
        "zone ": None,
        "zone Hallo": None,
        "zone 100": None,
    }

    assert {"zone", "zone Hallo", "zone 100"} == set(
        helpers.extract_domain_configs(config, "zone")
    )


def test_config_per_platform() -> None:
    """Test config per platform method."""
    config = OrderedDict(
        [
            ("zone", {"platform": "hello"}),
            ("zoner", None),
            ("zone Hallo", [1, {"platform": "hello 2"}]),
            ("zone 100", None),
        ]
    )

    assert [
        ("hello", config["zone"]),
        (None, 1),
        ("hello 2", config["zone Hallo"][1]),
    ] == list(helpers.config_per_platform(config, "zone"))
