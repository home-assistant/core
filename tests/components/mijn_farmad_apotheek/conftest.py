"""Fixtures for the Mijn Farmad Apotheek tests."""

from collections.abc import Generator
from unittest.mock import MagicMock, patch

import pytest

from . import get_mock_client


@pytest.fixture
def mock_farmad_client() -> Generator[MagicMock]:
    """Patch FarmadClient in the integration and the config flow."""
    client = get_mock_client()
    with (
        patch(
            "homeassistant.components.mijn_farmad_apotheek.FarmadClient",
            return_value=client,
        ) as mock_client,
        patch(
            "homeassistant.components.mijn_farmad_apotheek.config_flow.FarmadClient",
            return_value=client,
        ),
    ):
        yield mock_client


@pytest.fixture
def mock_setup_entry() -> Generator[MagicMock]:
    """Patch setup and unload to isolate config flow tests."""
    with (
        patch(
            "homeassistant.components.mijn_farmad_apotheek.async_setup_entry",
            return_value=None,
        ) as mock_setup,
        patch(
            "homeassistant.components.mijn_farmad_apotheek.async_unload_entry",
            return_value=None,
        ),
    ):
        yield mock_setup
