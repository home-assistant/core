"""Common fixtures for the Autarco tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, patch

from autarco import AccountSite, Inverter, Solar
import pytest

from homeassistant.components.autarco.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from tests.common import MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.autarco.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_autarco_client() -> Generator[AsyncMock]:
    """Mock a Autarco client."""
    with (
        patch(
            "homeassistant.components.autarco.Autarco",
            autospec=True,
        ) as mock_client,
        patch(
            "homeassistant.components.autarco.config_flow.Autarco",
            new=mock_client,
        ),
    ):
        client = mock_client.return_value
        client.get_account.return_value = [
            AccountSite(
                site_id=1,
                public_key="key-public",
                system_name="test-system",
                retailer="test-retailer",
                health="OK",
            )
        ]
        client.get_solar.return_value = Solar(
            power_production=200,
            energy_production_today=4,
            energy_production_month=58,
            energy_production_total=10379,
        )
        client.get_inverters.return_value = {
            "test-serial-1": Inverter(
                serial_number="test-serial-1",
                out_ac_power=200,
                out_ac_energy_total=10379,
                grid_turned_off=False,
                health="OK",
            ),
            "test-serial-2": Inverter(
                serial_number="test-serial-2",
                out_ac_power=500,
                out_ac_energy_total=10379,
                grid_turned_off=False,
                health="OK",
            ),
        }
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Autarco",
        data={
            CONF_EMAIL: "test@autarco.com",
            CONF_PASSWORD: "test-password",
        },
    )
