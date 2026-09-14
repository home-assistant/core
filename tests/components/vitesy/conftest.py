"""Common fixtures for the Vitesy tests."""

from aiovitesy.api import VitesyDevice
import pytest

from homeassistant.components.vitesy.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from tests.common import AsyncMock, Generator, MockConfigEntry, patch

DEVICE_ID = "80:65:99:34:F9:B4"
EMAIL = "test@example.com"


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.vitesy.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_devices() -> dict[str, VitesyDevice]:
    """Return a mocked Vitesy account holding a single device."""
    return {
        DEVICE_ID: VitesyDevice(
            device_id=DEVICE_ID,
            name="Kitchen Shelfy",
            model="SH02AA02",
            device_type="SHELFY-R1",
            firmware_version="1.2.3",
            connected=True,
            program_id="eco-s1",
            data={"id": DEVICE_ID},
            measurement={
                "score": 0.49045833333333333,
                "timestamp": "2026-09-10T17:19:38+02:00",
                "sensors_data": [
                    {
                        "id": "TMP01-SY",
                        "value": {"avg": 9.59, "min": 9.59, "max": 9.59},
                    },
                    {"id": "DOC-SY", "value": {"avg": 11, "min": 11, "max": 11}},
                    {"id": "DOT-SY", "value": {"avg": 205, "min": 205, "max": 205}},
                ],
                "status_data": [
                    {"id": "battery", "value": {"avg": 27, "min": 27, "max": 27}},
                    {"id": "charging", "value": False},
                    {"id": "mode", "value": "eco"},
                    {"id": "firmware", "value": "1.2.3"},
                ],
            },
            maintenance={
                "filter": {"due_date": "2026-08-02T06:45:07.623Z"},
                "fridge": {"due_date": "2026-10-31T06:45:07.623Z"},
            },
            programs={},
        )
    }


@pytest.fixture
def mock_vitesy_client(
    mock_devices: dict[str, VitesyDevice],
) -> Generator[AsyncMock]:
    """Mock the aiovitesy client used by the coordinator and the config flow."""
    with (
        patch(
            "homeassistant.components.vitesy.coordinator.VitesyApi", autospec=True
        ) as mock_client,
        patch("homeassistant.components.vitesy.config_flow.VitesyApi", new=mock_client),
    ):
        client = mock_client.return_value
        client.login = AsyncMock(return_value=None)
        client.get_all_devices = AsyncMock(return_value=mock_devices)
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=EMAIL,
        data={CONF_EMAIL: EMAIL, CONF_PASSWORD: "hunter2"},
        unique_id=EMAIL,
    )
