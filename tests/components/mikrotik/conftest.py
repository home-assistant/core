"""Mikrotik test configuration."""

from collections.abc import Callable, Generator
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from . import create_mock_config_entry

from tests.common import MockConfigEntry

type MockConfigEntryFactory = Callable[..., MockConfigEntry]
type MockCommandSideEffectFactory = Callable[
    [dict[str, Any], dict[str, dict[str, Any]], str],
    Callable[..., list[dict[str, Any]]],
]


@pytest.fixture
def mock_config_entry() -> MockConfigEntryFactory:
    """Create Mikrotik config entries with optional overrides."""
    return create_mock_config_entry


@pytest.fixture(autouse=True)
def mock_api() -> Generator[MagicMock]:
    """Mock the librouteros API instance returned by librouteros.connect."""
    api_instance = MagicMock()

    with patch("librouteros.connect", return_value=api_instance):
        yield api_instance


@pytest.fixture
def mock_command_side_effect() -> MockCommandSideEffectFactory:
    """Create a stateful librouteros command side_effect for the mocked API.

    Given mutable state, a mapping of command to the field updates it applies,
    and the command that reports current state, returns a callable to assign
    to `mock_api.side_effect` so tests can verify entity state that is driven
    by a coordinator refresh rather than an optimistic local update.
    """

    def _create(
        state: dict[str, Any],
        actions: dict[str, dict[str, Any]],
        print_cmd: str,
    ) -> Callable[..., list[dict[str, Any]]]:
        def _handler(cmd: str, **params: Any) -> list[dict[str, Any]]:
            if update := actions.get(cmd):
                state.update(update)
            elif cmd == print_cmd:
                return [dict(state)]
            return []

        return _handler

    return _create


@pytest.fixture
def mock_api_error(request: pytest.FixtureRequest) -> Generator[None]:
    """Mock librouteros.connect raising the parametrized error."""
    with patch("librouteros.connect", side_effect=request.param):
        yield
