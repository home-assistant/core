"""Fixtures for the AVM Fritz!Box integration."""

from unittest.mock import Mock, patch

import pytest


@pytest.fixture(name="fritz")
def fritz_fixture() -> Mock:
    """Patch libraries."""
    with (
        patch("homeassistant.components.fritzbox.coordinator.Fritzhome") as fritz,
        patch("homeassistant.components.fritzbox.config_flow.Fritzhome"),
    ):
        fritz.return_value.get_prefixed_host.return_value = "http://1.2.3.4"
        yield fritz
