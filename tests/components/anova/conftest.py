"""Common fixtures for Anova."""
from unittest.mock import AsyncMock, patch

from anova_wifi import (
    AnovaApi,
    AnovaException,
    AnovaPrecisionCooker,
    InvalidLogin,
    NoDevicesFound,
)
import pytest

from homeassistant.core import HomeAssistant

from . import DEVICE_UNIQUE_ID, ONLINE_UPDATE


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


@pytest.fixture
async def anova_precision_cooker(hass: HomeAssistant) -> AsyncMock:
    """Mock an APC object."""
    apc_patch = AsyncMock()

    async def apc_update_side_effect():
        apc_patch.status = ONLINE_UPDATE
        return ONLINE_UPDATE

    apc_patch.status = ONLINE_UPDATE
    apc_patch.update.side_effect = apc_update_side_effect
    apc_patch.device_key = "sample_key"
    apc_patch.type = "sample_type"

    with patch(
        "homeassistant.components.anova.AnovaPrecisionCooker", return_value=apc_patch
    ):
        yield apc_patch


@pytest.fixture
async def anova_precision_cooker_setter_failure(hass: HomeAssistant) -> AsyncMock:
    """Mock an APC object."""
    apc_patch = AsyncMock()

    async def apc_update_side_effect():
        apc_patch.status = ONLINE_UPDATE
        return ONLINE_UPDATE

    apc_patch.status = ONLINE_UPDATE
    apc_patch.update.side_effect = apc_update_side_effect
    apc_patch.device_key = "sample_key"
    apc_patch.type = "sample_type"

    async def apc_build_request_side_effect():
        raise AnovaException()

    async def apc_set_mode_side_effect(mode: str):
        raise AnovaException()

    async def apc_set_temperature_side_effect(temperature: float):
        raise AnovaException()

    apc_patch.build_request.side_effect = apc_build_request_side_effect
    apc_patch.set_mode.side_effect = apc_set_mode_side_effect
    apc_patch.set_target_temperature.side_effect = apc_set_temperature_side_effect
    with patch(
        "homeassistant.components.anova.AnovaPrecisionCooker", return_value=apc_patch
    ):
        yield apc_patch
