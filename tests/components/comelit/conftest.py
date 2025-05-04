"""Configure tests for Comelit SimpleHome."""

from copy import deepcopy

import pytest

from homeassistant.components.comelit.const import (
    BRIDGE,
    DOMAIN as COMELIT_DOMAIN,
    VEDO,
)
from homeassistant.const import CONF_HOST, CONF_PIN, CONF_PORT, CONF_TYPE

from .const import (
    BRIDGE_DEVICE_QUERY,
    BRIDGE_HOST,
    BRIDGE_PIN,
    BRIDGE_PORT,
    VEDO_DEVICE_QUERY,
    VEDO_HOST,
    VEDO_PIN,
    VEDO_PORT,
)

from tests.common import AsyncMock, Generator, MockConfigEntry, patch


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.comelit.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_serial_bridge() -> Generator[AsyncMock]:
    """Mock a Comelit serial bridge."""
    with (
        patch(
            "homeassistant.components.comelit.coordinator.ComeliteSerialBridgeApi",
            autospec=True,
        ) as mock_comelit_serial_bridge,
        patch(
            "homeassistant.components.comelit.config_flow.ComeliteSerialBridgeApi",
            new=mock_comelit_serial_bridge,
        ),
    ):
        bridge = mock_comelit_serial_bridge.return_value
        bridge.get_all_devices.return_value = deepcopy(BRIDGE_DEVICE_QUERY)
        bridge.host = BRIDGE_HOST
        bridge.port = BRIDGE_PORT
        bridge.device_pin = BRIDGE_PIN
        yield bridge


@pytest.fixture
def mock_serial_bridge_config_entry() -> Generator[MockConfigEntry]:
    """Mock a Comelit config entry for Comelit bridge."""
    return MockConfigEntry(
        domain=COMELIT_DOMAIN,
        data={
            CONF_HOST: BRIDGE_HOST,
            CONF_PORT: BRIDGE_PORT,
            CONF_PIN: BRIDGE_PIN,
            CONF_TYPE: BRIDGE,
        },
        entry_id="serial_bridge_config_entry_id",
    )


@pytest.fixture
def mock_vedo() -> Generator[AsyncMock]:
    """Mock a Comelit vedo."""
    with (
        patch(
            "homeassistant.components.comelit.coordinator.ComelitVedoApi",
            autospec=True,
        ) as mock_comelit_vedo,
        patch(
            "homeassistant.components.comelit.config_flow.ComelitVedoApi",
            new=mock_comelit_vedo,
        ),
    ):
        vedo = mock_comelit_vedo.return_value
        vedo.get_all_areas_and_zones.return_value = deepcopy(VEDO_DEVICE_QUERY)
        vedo.host = VEDO_HOST
        vedo.port = VEDO_PORT
        vedo.device_pin = VEDO_PIN
        vedo.type = VEDO
        yield vedo


@pytest.fixture
def mock_vedo_config_entry() -> Generator[MockConfigEntry]:
    """Mock a Comelit config entry for Comelit vedo."""
    return MockConfigEntry(
        domain=COMELIT_DOMAIN,
        data={
            CONF_HOST: VEDO_HOST,
            CONF_PORT: VEDO_PORT,
            CONF_PIN: VEDO_PIN,
            CONF_TYPE: VEDO,
        },
        entry_id="vedo_config_entry_id",
    )
