"""Tests for infrared compatibility helpers."""

from types import SimpleNamespace

import pytest

from homeassistant.components.itachip2ir import infrared_compat


def test_ensure_infrared_protocols_command_adds_missing_symbol(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test a fallback Command symbol is added when the dependency lacks one."""
    module = SimpleNamespace()

    monkeypatch.setattr(
        infrared_compat.importlib,
        "import_module",
        lambda name: module,
    )

    infrared_compat._ensure_infrared_protocols_command()

    assert module.Command is infrared_compat._InfraredProtocolsCommand


def test_ensure_infrared_protocols_command_keeps_existing_symbol(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test an existing Command symbol is not replaced."""
    existing_command = object()
    module = SimpleNamespace(Command=existing_command)

    monkeypatch.setattr(
        infrared_compat.importlib,
        "import_module",
        lambda name: module,
    )

    infrared_compat._ensure_infrared_protocols_command()

    assert module.Command is existing_command


def test_ensure_infrared_protocols_command_ignores_missing_dependency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Test the compatibility hook is a no-op if the package is unavailable."""

    def raise_import_error(name: str) -> None:
        raise ImportError(name)

    monkeypatch.setattr(
        infrared_compat.importlib,
        "import_module",
        raise_import_error,
    )

    infrared_compat._ensure_infrared_protocols_command()
