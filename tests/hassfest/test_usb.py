"""Tests for the hassfest usb plugin."""

import ast
from pathlib import Path

import pytest

from script.hassfest.model import Config, Integration
from script.hassfest.usb import generate_and_validate


@pytest.mark.parametrize(
    ("config_flow", "listed"),
    [
        pytest.param("SerialPortSelector()", True, id="name"),
        pytest.param("selector.SerialPortSelector()", True, id="attribute"),
        pytest.param("probatio.In(ports)", False, id="other_selector"),
        pytest.param(None, False, id="no_config_flow"),
    ],
)
def test_serial_port_selector_integrations(
    tmp_path: Path, config: Config, config_flow: str | None, listed: bool
) -> None:
    """Test listing the integrations whose config flow uses SerialPortSelector."""
    if config_flow is not None:
        (tmp_path / "config_flow.py").write_text(f"SCHEMA = {config_flow}\n")
    integration = Integration(tmp_path, _config=config, _manifest={"domain": "serial"})

    source = generate_and_validate({"serial": integration})

    value = next(
        node.value
        for node in ast.parse(source).body
        if isinstance(node, ast.Assign)
        and isinstance(node.targets[0], ast.Name)
        and node.targets[0].id == "SERIAL_PORT_SELECTOR_INTEGRATIONS"
    )
    assert ast.literal_eval(value) == (["serial"] if listed else [])
