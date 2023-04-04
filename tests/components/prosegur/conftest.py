"""Define test fixtures for Prosegur."""
from unittest.mock import AsyncMock, MagicMock, patch

from pyprosegur.installation import Camera
import pytest

from homeassistant.components.prosegur import DOMAIN as PROSEGUR_DOMAIN
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

CONTRACT = "1234abcd"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=PROSEGUR_DOMAIN,
        data={
            "contract": CONTRACT,
            CONF_USERNAME: "user@email.com",
            CONF_PASSWORD: "password",
            "country": "PT",
        },
    )


@pytest.fixture
def mock_install() -> AsyncMock:
    """Return the mocked alarm install."""
    install = MagicMock()
    install.contract = CONTRACT
    install.cameras = [Camera("1", "test_cam")]
    install.arm = AsyncMock()
    install.disarm = AsyncMock()
    install.arm_partially = AsyncMock()
    install.get_image = AsyncMock(return_value=b"ABC")
    install.request_image = AsyncMock()

    install.data = {"contract": CONTRACT}
    install.activity = AsyncMock(return_value={"event": "armed"})

    return install


@pytest.fixture
async def init_integration(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry, mock_install: AsyncMock
) -> MockConfigEntry:
    """Set up the Prosegur integration for testing."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "pyprosegur.installation.Installation.retrieve", return_value=mock_install
    ), patch("pyprosegur.auth.Auth.login"):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        return mock_config_entry
