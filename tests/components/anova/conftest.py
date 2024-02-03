"""Common fixtures for Anova."""
from unittest.mock import patch

from anova_wifi import AnovaApi, InvalidLogin, NoDevicesFound
from anova_wifi.mocks.anova_api import anova_api_mock
import pytest

from homeassistant.core import HomeAssistant


@pytest.fixture
async def anova_api(
    hass: HomeAssistant,
) -> AnovaApi:
    """Mock the api for Anova."""
    api_mock = anova_api_mock()

    with patch("homeassistant.components.anova.AnovaApi", return_value=api_mock), patch(
        "homeassistant.components.anova.config_flow.AnovaApi", return_value=api_mock
    ):
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
    api_mock = anova_api_mock()

    api_mock.create_websocket.side_effect = NoDevicesFound
    with patch("homeassistant.components.anova.AnovaApi", return_value=api_mock), patch(
        "homeassistant.components.anova.config_flow.AnovaApi", return_value=api_mock
    ):
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
    api_mock = anova_api_mock()

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


@pytest.fixture
async def anova_api_no_data(
    hass: HomeAssistant,
) -> AnovaApi:
    """Mock the api for Anova with a wrong login."""
    api_mock = anova_api_mock(post_connect_messages=[])

    with patch("homeassistant.components.anova.AnovaApi", return_value=api_mock):
        api = AnovaApi(
            None,
            "sample@gmail.com",
            "sample",
        )
        yield api
