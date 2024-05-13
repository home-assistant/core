"""Common fixtures for Anova."""
from unittest.mock import AsyncMock, patch

from anova_wifi import AnovaApi, AnovaPrecisionCooker, InvalidLogin, NoDevicesFound
import pytest

from homeassistant.core import HomeAssistant

from . import DEVICE_UNIQUE_ID


@pytest.fixture
async def anova_api(
    hass: HomeAssistant,
) -> AnovaApi:
    """Mock the api for Anova."""
    api_mock = AsyncMock()

    new_device = AnovaPrecisionCooker(None, DEVICE_UNIQUE_ID, "type_sample", None)

    async def authenticate_side_effect():
        api_mock.jwt = "my_test_jwt"

    async def get_devices_side_effect():
        if not api_mock.existing_devices:
            api_mock.existing_devices = []
        api_mock.existing_devices = api_mock.existing_devices + [new_device]
        return [new_device]

    api_mock.authenticate.side_effect = authenticate_side_effect
    api_mock.get_devices.side_effect = get_devices_side_effect

    with patch("homeassistant.components.anova.AnovaApi", return_value=api_mock):
        api = AnovaApi(
            None,
            "sample@gmail.com",
            "sample",
        )
        yield api


@pytest.fixture
async def anova_api_no_devices(
    hass: HomeAssistant,
) -> AnovaApi:
    """Mock the api for Anova with no online devices."""
    api_mock = AsyncMock()

    async def authenticate_side_effect():
        api_mock.jwt = "my_test_jwt"

    async def get_devices_side_effect():
        raise NoDevicesFound()

    api_mock.authenticate.side_effect = authenticate_side_effect
    api_mock.get_devices.side_effect = get_devices_side_effect

    with patch("homeassistant.components.anova.AnovaApi", return_value=api_mock):
        api = AnovaApi(
            None,
            "sample@gmail.com",
            "sample",
        )
        yield api


@pytest.fixture
async def anova_api_wrong_login(
    hass: HomeAssistant,
) -> AnovaApi:
    """Mock the api for Anova with a wrong login."""
    api_mock = AsyncMock()

    async def authenticate_side_effect():
        raise InvalidLogin()

    api_mock.authenticate.side_effect = authenticate_side_effect

    with patch("homeassistant.components.anova.AnovaApi", return_value=api_mock):
        api = AnovaApi(
            None,
            "sample@gmail.com",
            "sample",
        )
        yield api
