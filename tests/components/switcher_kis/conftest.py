"""Common fixtures and objects for the Switcher integration tests."""

from unittest.mock import AsyncMock, Mock, patch

import pytest


@pytest.fixture
def mock_bridge(request):
    """Return a mocked SwitcherBridge."""
    with patch(
        "homeassistant.components.switcher_kis.utils.SwitcherBridge", autospec=True
    ) as bridge_mock:
        bridge = bridge_mock.return_value

        bridge.devices = []
        if hasattr(request, "param") and request.param:
            bridge.devices = request.param

        async def start():
            bridge.is_running = True

            for device in bridge.devices:
                bridge_mock.call_args[0][0](device)

        def mock_callbacks(devices):
            for device in devices:
                bridge_mock.call_args[0][0](device)

        async def stop():
            bridge.is_running = False

        bridge.start = AsyncMock(side_effect=start)
        bridge.mock_callbacks = Mock(side_effect=mock_callbacks)
        bridge.stop = AsyncMock(side_effect=stop)

        yield bridge


@pytest.fixture
def mock_api():
    """Fixture for mocking aioswitcher.api.SwitcherApi."""
    api_mock = AsyncMock()

    patchers = [
        patch(
            "homeassistant.components.switcher_kis.switch.SwitcherType1Api.connect",
            new=api_mock,
        ),
        patch(
            "homeassistant.components.switcher_kis.switch.SwitcherType1Api.disconnect",
            new=api_mock,
        ),
        patch(
            "homeassistant.components.switcher_kis.climate.SwitcherType2Api.connect",
            new=api_mock,
        ),
        patch(
            "homeassistant.components.switcher_kis.climate.SwitcherType2Api.disconnect",
            new=api_mock,
        ),
    ]

    for patcher in patchers:
        patcher.start()

    yield api_mock

    for patcher in patchers:
        patcher.stop()
