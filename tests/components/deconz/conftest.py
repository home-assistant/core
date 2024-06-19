"""deconz conftest."""

from __future__ import annotations

from unittest.mock import patch

from pydeconz.websocket import Signal
import pytest

from tests.components.light.conftest import mock_light_profiles  # noqa: F401


@pytest.fixture(autouse=True)
def mock_deconz_websocket():
    """No real websocket allowed."""
    with patch("pydeconz.gateway.WSClient") as mock:

        async def make_websocket_call(data: dict | None = None, state: str = ""):
            """Generate a websocket call."""
            pydeconz_gateway_session_handler = mock.call_args[0][3]

            if data:
                mock.return_value.data = data
                await pydeconz_gateway_session_handler(signal=Signal.DATA)
            elif state:
                mock.return_value.state = state
                await pydeconz_gateway_session_handler(signal=Signal.CONNECTION_STATE)
            else:
                raise NotImplementedError

        yield make_websocket_call
