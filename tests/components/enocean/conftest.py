"""Fixtures for EnOcean integration tests."""

from unittest.mock import Mock

import pytest

from tests.common import MockConfigEntry


@pytest.fixture(name="mock_gateway")
def mock_gateway_fixture() -> MockConfigEntry:
    """Return the default mocked config entry."""

    gateway = Mock(
        mock_devices=[],
    )

    # with patch(f"{TRADFRI_PATH}.Gateway", return_value=gateway), patch(
    #     f"{TRADFRI_PATH}.config_flow.Gateway", return_value=gateway
    # ):
    yield gateway
