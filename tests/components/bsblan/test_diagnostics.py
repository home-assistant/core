"""Tests for the diagnostics data provided by the BSBLan integration."""

import logging
from unittest.mock import AsyncMock, MagicMock, patch

from aiohttp import ClientResponse, ClientSession
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.bsblan import DOMAIN
from homeassistant.components.bsblan.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.components.bsblan.models import BSBLanCoordinatorData, BSBLanData
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from tests.common import MockConfigEntry
from tests.typing import ClientSessionGenerator

_LOGGER = logging.getLogger(__name__)


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    # Create a mock config entry
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "127.0.0.1",
            CONF_PORT: 80,
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
        },
        entry_id="test_entry_id",
    )

    # Create mock state and sensor data
    mock_state = MagicMock()
    mock_state.to_dict.return_value = {"state": "mocked_state"}
    mock_sensor = MagicMock()
    mock_sensor.to_dict.return_value = {"sensor": "mocked_sensor"}

    # Create mock coordinator data
    mock_coordinator_data = BSBLanCoordinatorData(state=mock_state, sensor=mock_sensor)

    # Create mock coordinator
    mock_coordinator = MagicMock()
    mock_coordinator.data = mock_coordinator_data

    # Create mock device, info, and static data
    mock_device = MagicMock()
    mock_device.to_dict.return_value = {"device": "mocked_device"}
    mock_info = MagicMock()
    mock_info.to_dict.return_value = {"info": "mocked_info"}
    mock_static = MagicMock()
    mock_static.to_dict.return_value = {"static": "mocked_static"}

    # Create mock BSBLAN data
    mock_bsblan_data = BSBLanData(
        coordinator=mock_coordinator,
        client=MagicMock(),
        device=mock_device,
        info=mock_info,
        static=mock_static,
    )

    # Add the config entry to hass
    config_entry.add_to_hass(hass)
    hass.data[DOMAIN] = {config_entry.entry_id: mock_bsblan_data}

    # Set up the BSBLAN integration
    with patch("homeassistant.components.bsblan.async_setup_entry", return_value=True):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Ensure the diagnostics component is set up
    assert await async_setup_component(hass, "diagnostics", {})
    await hass.async_block_till_done()

    # Mock the client session and response
    mock_client_session = MagicMock(spec=ClientSession)
    mock_response = MagicMock(spec=ClientResponse)
    mock_response.status = 200
    mock_response.json = AsyncMock(
        return_value={
            "coordinator_data": {
                "state": {"state": "mocked_state"},
                "sensor": {"sensor": "mocked_sensor"},
            },
            "device": {"device": "mocked_device"},
            "info": {"info": "mocked_info"},
            "static": {"static": "mocked_static"},
        }
    )
    mock_client_session.get = AsyncMock(return_value=mock_response)


async def test_diagnostics_to_dict_scenarios(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test diagnostics with different to_dict scenarios."""

    class AwaitableResult:
        def __await__(self):
            async def async_result():
                return {"awaitable": "result"}

            return async_result().__await__()

    class MockWithAwaitableToDict:
        def to_dict(self):
            return AwaitableResult()

    class MockWithRegularToDict:
        def to_dict(self):
            return {"regular": "result"}

    class MockWithoutToDict:
        pass

    mock_state = MockWithAwaitableToDict()
    mock_sensor = MockWithRegularToDict()
    mock_device = MockWithoutToDict()

    mock_coordinator_data = BSBLanCoordinatorData(
        state=mock_state,
        sensor=mock_sensor,
    )

    mock_coordinator = MagicMock()
    mock_coordinator.data = mock_coordinator_data

    mock_data = BSBLanData(
        coordinator=mock_coordinator,
        client=MagicMock(),
        device=mock_device,
        info=MockWithAwaitableToDict(),
        static=MockWithRegularToDict(),
    )

    hass.data[DOMAIN] = {mock_config_entry.entry_id: mock_data}

    diagnostics_data = await async_get_config_entry_diagnostics(hass, mock_config_entry)

    expected_data = {
        "info": {"awaitable": "result"},
        "device": mock_device,  # This should be the object itself
        "coordinator_data": {
            "state": {"awaitable": "result"},
            "sensor": {"regular": "result"},
        },
        "static": {"regular": "result"},
    }

    assert diagnostics_data == expected_data


async def test_diagnostics_no_to_dict(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test diagnostics when to_dict is callable but returns a mock."""
    mock_state = MagicMock()
    mock_state.to_dict.return_value = "state_string"
    mock_sensor = MagicMock()
    mock_sensor.to_dict.return_value = "sensor_string"

    mock_coordinator_data = BSBLanCoordinatorData(
        state=mock_state,
        sensor=mock_sensor,
    )

    mock_coordinator = MagicMock()
    mock_coordinator.data = mock_coordinator_data

    mock_device = MagicMock()
    mock_device.to_dict.return_value = "device_string"
    mock_info = MagicMock()
    mock_info.to_dict.return_value = "info_string"
    mock_static = MagicMock()
    mock_static.to_dict.return_value = "static_string"

    mock_data = BSBLanData(
        coordinator=mock_coordinator,
        client=MagicMock(),
        device=mock_device,
        info=mock_info,
        static=mock_static,
    )

    hass.data[DOMAIN] = {mock_config_entry.entry_id: mock_data}

    # Mock the format_mac function to return a predictable value
    with patch(
        "homeassistant.helpers.device_registry.format_mac",
        return_value="00:11:22:33:44:55",
    ):
        diagnostics_data = (
            await hass.components.bsblan.diagnostics.async_get_config_entry_diagnostics(
                hass, mock_config_entry
            )
        )

    expected_data = {
        "info": "info_string",
        "device": "device_string",
        "coordinator_data": {
            "state": "state_string",
            "sensor": "sensor_string",
        },
        "static": "static_string",
    }

    assert diagnostics_data == expected_data
