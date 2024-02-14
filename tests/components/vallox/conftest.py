"""Common utilities for Vallox tests."""

import random
import string
from typing import Any
from unittest.mock import MagicMock, patch
from uuid import UUID

import pytest
from vallox_websocket_api.vallox import (
    MODEL_METRIC,
    PROFILE,
    SW_VERSION_METRICS,
    MetricData,
)

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


def default_metrics():
    """Return default metrics."""
    return {
        MODEL_METRIC: "Vallox Testmodel",
        SW_VERSION_METRICS[0]: "0",
        SW_VERSION_METRICS[1]: ".",
        SW_VERSION_METRICS[2]: "1",
        SW_VERSION_METRICS[3]: ".",
        SW_VERSION_METRICS[4]: "2",
    }


def patch_metrics(metrics: dict[str, Any]):
    """Patch the Vallox metrics response."""
    metric_data = MagicMock(MetricData)
    metric_data.uuid = MagicMock(return_value=_random_uuid())
    metric_data.model = MagicMock(return_value="Vallox Testmodel")
    metric_data.sw_version = MagicMock(return_value="0.1.2")

    return patch(
        "homeassistant.components.vallox.Vallox.fetch_metric_data",
        return_value=metric_data,
    )


def patch_profile(profile: PROFILE):
    """Patch the Vallox metrics response."""
    return patch(
        "homeassistant.components.vallox.MetricData.profile",
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
    metric_data = MagicMock(MetricData)
    metric_data.uuid = MagicMock(return_value=_random_uuid())
    metric_data.model = MagicMock(return_value="Vallox Testmodel")
    metric_data.sw_version = MagicMock(return_value="0.1.2")

    with patch(
        "homeassistant.components.vallox.Vallox.fetch_metric_data",
        return_value=metric_data,
    ):
        yield


# @pytest.fixture(autouse=True)
# def patch_default_profile():
#    """Patch the Vallox profile response."""
#    with patch(
#        "homeassistant.components.vallox.MetricData.profile",
#        return_value=PROFILE.HOME,
#    ):
#        yield


# @pytest.fixture(autouse=True)
# def patch_model():
#    """Patch the Vallox model response."""
#    with patch(
#        "homeassistant.components.vallox.MetricData.model",
#        return_value="Vallox Testmodel",
#    ):
#        yield


# @pytest.fixture(autouse=True)
# def patch_sw_version():
#    """Patch the Vallox SW version response."""
#    with patch(
#        "homeassistant.components.vallox.MetricData.sw_version",
#        return_value="0.1.2",
#    ):
#        yield


# @pytest.fixture(autouse=True)
# def patch_uuid():
#    """Patch the Vallox UUID response."""
#    with patch(
#        "homeassistant.components.vallox.MetricData.uuid",
#        return_value=_random_uuid(),
#    ):
#        yield


def _random_uuid() -> UUID:
    """Generate a random UUID."""
    uuid = "".join(random.choices(string.hexdigits, k=32))
    return UUID(uuid)
