"""Tests for the serial_port_selector usb dependency pylint plugin."""

from __future__ import annotations

import json
from pathlib import Path

import astroid
from pylint.checkers import BaseChecker
from pylint.testutils.unittest_linter import UnittestLinter
import pytest

from tests.pylint import assert_no_messages, walk_checker


def _write_integration(tmp_path: Path, domain: str, manifest: dict) -> Path:
    """Create an integration directory with a manifest and config_flow."""
    integration_dir = tmp_path / "homeassistant" / "components" / domain
    integration_dir.mkdir(parents=True)
    (integration_dir / "config_flow.py").touch()
    (integration_dir / "manifest.json").write_text(json.dumps(manifest))
    return integration_dir


def test_serial_port_selector_with_usb_dependency(
    linter: UnittestLinter,
    enforce_serial_port_selector_usb_checker: BaseChecker,
    tmp_path: Path,
) -> None:
    """A config flow declaring usb as a hard dependency is not flagged."""
    integration_dir = _write_integration(
        tmp_path, "my_device", {"domain": "my_device", "dependencies": ["usb"]}
    )

    code = """
    vol.Schema({vol.Required(CONF_PORT): SerialPortSelector()})
    """
    root_node = astroid.parse(code, "homeassistant.components.my_device.config_flow")
    root_node.file = str(integration_dir / "config_flow.py")

    with assert_no_messages(linter):
        walk_checker(linter, enforce_serial_port_selector_usb_checker, root_node)


@pytest.mark.parametrize(
    ("code", "module_name"),
    [
        pytest.param(
            """
        vol.Schema({vol.Required(CONF_HOST): TextSelector()})
        """,
            "homeassistant.components.my_device.config_flow",
            id="other_selector",
        ),
        pytest.param(
            """
        SerialPortSelector()
        """,
            "homeassistant.components.my_device.sensor",
            id="not_config_flow",
        ),
    ],
)
def test_serial_port_selector_not_flagged(
    linter: UnittestLinter,
    enforce_serial_port_selector_usb_checker: BaseChecker,
    tmp_path: Path,
    code: str,
    module_name: str,
) -> None:
    """Cases that must not be flagged even without a usb dependency."""
    integration_dir = _write_integration(tmp_path, "my_device", {"domain": "my_device"})

    root_node = astroid.parse(code, module_name)
    root_node.file = str(integration_dir / f"{module_name.rsplit('.', 1)[1]}.py")

    with assert_no_messages(linter):
        walk_checker(linter, enforce_serial_port_selector_usb_checker, root_node)


@pytest.mark.parametrize(
    "manifest",
    [
        pytest.param({"domain": "my_device"}, id="no_dependency"),
        pytest.param(
            {"domain": "my_device", "after_dependencies": ["usb"]},
            id="after_dependencies_only",
        ),
    ],
)
def test_serial_port_selector_without_usb_dependency(
    linter: UnittestLinter,
    enforce_serial_port_selector_usb_checker: BaseChecker,
    tmp_path: Path,
    manifest: dict,
) -> None:
    """A config flow without usb as a hard dependency is flagged once."""
    integration_dir = _write_integration(tmp_path, "my_device", manifest)

    code = """
    vol.Schema({
        vol.Required(CONF_PORT): SerialPortSelector(),
        vol.Optional(CONF_OTHER): SerialPortSelector(),
    })
    """
    root_node = astroid.parse(code, "homeassistant.components.my_device.config_flow")
    root_node.file = str(integration_dir / "config_flow.py")

    walk_checker(linter, enforce_serial_port_selector_usb_checker, root_node)
    messages = linter.release_messages()
    assert len(messages) == 1
    assert messages[0].msg_id == "home-assistant-serial-port-selector-usb-dependency"
