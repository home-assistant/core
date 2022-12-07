"""Common utilities for Vallox tests."""

import random
import string
from typing import Any
from unittest.mock import patch
from uuid import UUID

import pytest
from vallox_websocket_api.vallox import PROFILE

from homeassistant.components.vallox.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_NAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture
def mock_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Create mocked Vallox config entry."""
    vallox_mock_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.100.50",
            CONF_NAME: "Vallox",
        },
    )
    vallox_mock_entry.add_to_hass(hass)

    return vallox_mock_entry


def patch_metrics(metrics: dict[str, Any]):
    """Patch the Vallox metrics response."""
    return patch(
        "homeassistant.components.vallox.Vallox.fetch_metrics",
        return_value=metrics,
    )


def patch_profile(profile: PROFILE):
    """Patch the Vallox metrics response."""
    return patch(
        "homeassistant.components.vallox.Vallox.get_profile",
        return_value=profile,
    )


def patch_profile_set():
    """Patch the Vallox metrics set values."""
    return patch("homeassistant.components.vallox.Vallox.set_profile")


def patch_metrics_set():
    """Patch the Vallox metrics set values."""
    return patch("homeassistant.components.vallox.Vallox.set_values")


@pytest.fixture(autouse=True)
def patch_empty_metrics():
    """Patch the Vallox profile response."""
    with patch(
        "homeassistant.components.vallox.Vallox.fetch_metrics",
        return_value={},
    ):
        yield


@pytest.fixture(autouse=True)
def patch_default_profile():
    """Patch the Vallox profile response."""
    with patch(
        "homeassistant.components.vallox.Vallox.get_profile",
        return_value=PROFILE.HOME,
    ):
        yield


@pytest.fixture(autouse=True)
def patch_model():
    """Patch the Vallox model response."""
    with patch(
        "homeassistant.components.vallox._api_get_model",
        return_value="Vallox Testmodel",
    ):
        yield


@pytest.fixture(autouse=True)
def patch_sw_version():
    """Patch the Vallox SW version response."""
    with patch(
        "homeassistant.components.vallox._api_get_sw_version",
        return_value="0.1.2",
    ):
        yield


@pytest.fixture(autouse=True)
def patch_uuid():
    """Patch the Vallox UUID response."""
    with patch(
        "homeassistant.components.vallox._api_get_uuid",
        return_value=_random_uuid(),
    ):
        yield


def _random_uuid():
    """Generate a random UUID."""
    uuid = "".join(random.choices(string.hexdigits, k=32))
    return UUID(uuid)
