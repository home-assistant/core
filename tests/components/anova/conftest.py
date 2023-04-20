"""Common fixtures for Anova."""
from unittest.mock import AsyncMock, patch

from anova_wifi import AnovaApi, AnovaPrecisionCooker
import pytest

from homeassistant.core import HomeAssistant

from . import DEVICE_UNIQUE_ID


@pytest.fixture
async def anova_api(
    hass: HomeAssistant,
):
    """Mock the api for Anova."""
    api_mock = AsyncMock()

    async def authenticate_side_effect():
        api_mock.jwt = "my_test_jwt"

    api_mock.authenticate.side_effect = authenticate_side_effect
    api_mock.get_devices.return_value = [
        AnovaPrecisionCooker(None, DEVICE_UNIQUE_ID, "type_sample", None)
    ]

    with patch("homeassistant.components.anova.AnovaApi", return_value=api_mock):
        api = AnovaApi(
            None,
            "sample@gmail.com",
            "sample",
        )
        yield api
