"""Tests for hassfest barcode."""

from pathlib import Path

import probatio
import pytest

from script.hassfest import barcode
from script.hassfest.manifest import verify_barcode_prefix
from script.hassfest.model import Config, Integration


@pytest.mark.parametrize(
    ("config_flow", "expected_matchers", "expected_errors"),
    [
        pytest.param(
            True,
            '"data": "X-HM://*",\n        "domain": "test",',
            [],
            id="config_flow",
        ),
        pytest.param(
            False,
            "BARCODE = []",
            ["Integrations with barcode matchers need a config flow"],
            id="no_config_flow",
        ),
    ],
)
def test_generate_and_validate(
    config: Config,
    config_flow: bool,
    expected_matchers: str,
    expected_errors: list[str],
) -> None:
    """Test barcode matchers are only generated for integrations with a flow."""
    integration = Integration(
        path=Path("homeassistant/components/test").absolute(),
        _config=config,
        _manifest={
            "domain": "test",
            "config_flow": config_flow,
            "barcode": [{"data": "X-HM://*"}],
        },
    )

    content = barcode.generate_and_validate({"test": integration})

    assert expected_matchers in content
    assert [error.error for error in integration.errors] == expected_errors


@pytest.mark.parametrize(
    "value", ["8719514342620", "87115604*", "900[01]*", "X-HM://*", "MT:*"]
)
def test_verify_barcode_prefix(value: str) -> None:
    """Test specific barcode matchers are accepted."""
    assert verify_barcode_prefix(value) == value


@pytest.mark.parametrize("value", ["*", "9*", "90*", "8?1*", "8[01]*"])
def test_verify_barcode_prefix_too_broad(value: str) -> None:
    """Test barcode matchers that would claim unrelated barcodes are rejected."""
    with pytest.raises(probatio.Invalid, match="needs at least 3 characters"):
        verify_barcode_prefix(value)
