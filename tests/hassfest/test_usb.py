"""Tests for the hassfest usb plugin."""

from pathlib import Path

import pytest

from script.hassfest.model import Config, Integration
from script.hassfest.usb import _uses_serial_port_selector


@pytest.mark.parametrize(
    ("config_flow", "expected"),
    [
        pytest.param("SerialPortSelector()", True, id="name"),
        pytest.param("selector.SerialPortSelector()", True, id="attribute"),
        pytest.param("probatio.In(ports)", False, id="other_selector"),
    ],
)
def test_uses_serial_port_selector(
    tmp_path: Path, config: Config, config_flow: str, expected: bool
) -> None:
    """Test detecting SerialPortSelector in a config flow."""
    (tmp_path / "config_flow.py").write_text(f"SCHEMA = {config_flow}\n")
    integration = Integration(tmp_path, _config=config, _manifest={"domain": "serial"})

    assert _uses_serial_port_selector(integration) is expected


def test_uses_serial_port_selector_without_config_flow(
    tmp_path: Path, config: Config
) -> None:
    """Test an integration without a config flow does not use SerialPortSelector."""
    integration = Integration(tmp_path, _config=config, _manifest={"domain": "serial"})

    assert _uses_serial_port_selector(integration) is False
