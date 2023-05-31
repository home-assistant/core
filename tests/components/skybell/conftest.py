"""Test setup for the SkyBell integration."""

from unittest.mock import AsyncMock, patch

from aioskybell import Skybell, SkybellDevice
import pytest

from . import USER_ID


@pytest.fixture(autouse=True)
def skybell_mock():
    """Fixture for our skybell tests."""
    mocked_skybell_device = AsyncMock(spec=SkybellDevice)

    mocked_skybell = AsyncMock(spec=Skybell)
    mocked_skybell.async_get_devices.return_value = [mocked_skybell_device]
    mocked_skybell.async_send_request.return_value = {"id": USER_ID}
    mocked_skybell.user_id = USER_ID

    with patch(
        "homeassistant.components.skybell.config_flow.Skybell",
        return_value=mocked_skybell,
    ), patch("homeassistant.components.skybell.Skybell", return_value=mocked_skybell):
        yield mocked_skybell
