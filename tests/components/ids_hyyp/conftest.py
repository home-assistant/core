"""Define fixtures available for all tests."""
from unittest.mock import MagicMock, patch

from pyhyypapi import HyypClient
from pytest import fixture

MOCK_API_RETURN = {"token": "12341"}


@fixture
def ids_hyyp_config_flow(hass):
    """Mock the ids_hyyp API for easier config flow testing."""
    with patch.object(HyypClient, "login", return_value=True), patch(
        "homeassistant.components.ids_hyyp.config_flow.HyypClient"
    ) as mock_ids_hyyp:
        instance = mock_ids_hyyp.return_value = HyypClient(
            "test-email",
            "test-password",
            "com.hyyp247.home",
        )

        instance.login = MagicMock(return_value=MOCK_API_RETURN)

        yield mock_ids_hyyp
