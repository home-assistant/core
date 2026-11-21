"""Fixtures for PiKVM integration tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from pikvm_aio import PiKVMDeviceInfo
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_load_json_object_fixture

from homeassistant.components.pikvm.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant

SERIAL = "0000000012345678"


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        title="pikvm",
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.50",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "secret",
            CONF_VERIFY_SSL: False,
        },
        unique_id=SERIAL,
    )


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.pikvm.async_setup_entry", return_value=None
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
async def device_info(
    hass: HomeAssistant, request: pytest.FixtureRequest
) -> PiKVMDeviceInfo:
    """Return device info from a sanitized PiKVM V3 API response.

    Parametrize indirectly with a top-level section name to simulate missing hardware.
    """
    data = await async_load_json_object_fixture(hass, "info.json", DOMAIN)
    data["msd"] = await async_load_json_object_fixture(hass, "msd.json", DOMAIN)
    if missing := getattr(request, "param", None):
        if missing == "health":
            del data["hw"]["health"]
        else:
            del data[missing]
    return PiKVMDeviceInfo.from_dict(data)


@pytest.fixture
def mock_pikvm_client_class(device_info: PiKVMDeviceInfo) -> Generator[MagicMock]:
    """Return the mocked PiKVM client class."""
    with patch(
        "homeassistant.components.pikvm.coordinator.PiKVMClient", autospec=True
    ) as mock_class:
        mock_class.return_value.get_info.return_value = device_info
        yield mock_class


@pytest.fixture
def mock_pikvm_client(mock_pikvm_client_class: MagicMock) -> MagicMock:
    """Return the mocked PiKVM client."""
    return mock_pikvm_client_class.return_value


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_pikvm_client: MagicMock,
) -> MockConfigEntry:
    """Set up the PiKVM integration for testing."""
    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    return mock_config_entry
