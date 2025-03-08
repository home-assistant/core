"""Common fixtures for the airios integration tests."""

from pyairios import ProductId
import pytest

from homeassistant import config_entries
from homeassistant.components.airios.const import (
    CONF_BRIDGE_RF_ADDRESS,
    CONF_RF_ADDRESS,
    DOMAIN,
    BridgeType,
)
from homeassistant.const import CONF_DEVICE, CONF_NAME, CONF_SLAVE, CONF_TYPE
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


@pytest.fixture(name="mock_config_entry")
def fixture_mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Return a mock config entry."""
    rf_address = 11259375
    return MockConfigEntry(
        title="Airios RF bridge (ABCDEF)",
        domain=DOMAIN,
        version=1,
        data={
            CONF_DEVICE: "/dev/ttyACM9",
            CONF_SLAVE: 207,
            CONF_TYPE: BridgeType.SERIAL,
            CONF_BRIDGE_RF_ADDRESS: rf_address,
        },
        entry_id="3bd2acb0e4f0476d40865546d0d91922",
        unique_id=str(rf_address),
    )


@pytest.fixture(name="mock_config_entry_ctrl")
def fixture_mock_config_entry_ctrl(hass: HomeAssistant) -> MockConfigEntry:
    """Return a mock config entry."""
    rf_address = 11259375
    return MockConfigEntry(
        title="Airios RF bridge (ABCDEF)",
        domain=DOMAIN,
        version=1,
        data={
            CONF_DEVICE: "/dev/ttyACM9",
            CONF_SLAVE: 207,
            CONF_TYPE: BridgeType.SERIAL,
            CONF_BRIDGE_RF_ADDRESS: rf_address,
        },
        entry_id="3bd2acb0e4f0476d40865546d0d91922",
        unique_id=str(rf_address),
        subentries_data=[
            config_entries.ConfigSubentryData(
                data={
                    CONF_SLAVE: 2,
                    CONF_NAME: "Mock controller",
                    CONF_DEVICE: ProductId.VMD_02RPS78,
                    CONF_RF_ADDRESS: 123456,
                },
                subentry_type="controller",
                title="Controller",
                unique_id="123456",
            )
        ],
    )
