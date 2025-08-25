"""Tests for the Fluss Buttons."""

from unittest.mock import create_autospec, patch

from fluss_api import FlussApiClient
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.button import DOMAIN as BUTTON_DOMAIN, SERVICE_PRESS
from homeassistant.config_entries import MockConfigEntry
from homeassistant.const import ATTR_ENTITY_ID
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er


@pytest.fixture
def mock_api_client() -> FlussApiClient:
    """Mock API Client."""
    client = create_autospec(FlussApiClient, instance=True)
    client.async_get_devices.return_value = {"devices": [{"deviceId": "1", "deviceName": "Test Device"}]}
    return client


@pytest.fixture
async def init_integration(
    hass: HomeAssistant,
    mock_api_client: FlussApiClient,
) -> MockConfigEntry:
    """Set up the Fluss integration for testing."""
    entry = MockConfigEntry(
        domain="fluss",
        data={"api_key": "test_api_key"},
    )
    entry.add_to_hass(hass)

    with patch(
        "fluss_api.main.FlussApiClient",
        return_value=mock_api_client,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    return entry


async def test_button(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_api_client: FlussApiClient,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the Fluss button."""

    state = hass.states.get("button.test_device")
    assert state
    assert state == snapshot

    entry = entity_registry.async_get(state.entity_id)
    assert entry
    assert entry == snapshot

    await hass.services.async_call(
        BUTTON_DOMAIN,
        SERVICE_PRESS,
        {
            ATTR_ENTITY_ID: "button.test_device",
        },
        blocking=True,
    )

    mock_api_client.async_trigger_device.assert_called_once_with("1")


async def test_button_error(
    hass: HomeAssistant,
    init_integration: MockConfigEntry,
    mock_api_client: FlussApiClient,
) -> None:
    """Test the Fluss button error."""
    state = hass.states.get("button.test_device")
    assert state

    mock_api_client.async_trigger_device.side_effect = Exception("Boom.")
    with pytest.raises(HomeAssistantError) as exc_info:
        await hass.services.async_call(
            BUTTON_DOMAIN,
            SERVICE_PRESS,
            {
                ATTR_ENTITY_ID: "button.test_device",
            },
            blocking=True,
        )
    assert exc_info.value.translation_key == "button_error"


async def test_no_devices(
    hass: HomeAssistant,
    mock_api_client: FlussApiClient,
) -> None:
    """Test setup when no devices are returned."""
    mock_api_client.async_get_devices.return_value = {"devices": []}

    entry = MockConfigEntry(
        domain="fluss",
        data={"api_key": "test_api_key"},
    )
    entry.add_to_hass(hass)

    with patch(
        "fluss_api.main.FlussApiClient",
        return_value=mock_api_client,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("button.test_device")
    assert state is None


async def test_setup_exception(
    hass: HomeAssistant,
    mock_api_client: FlussApiClient,
) -> None:
    """Test setup entry when async_get_devices raises an exception."""
    mock_api_client.async_get_devices.side_effect = Exception("Unexpected error")

    entry = MockConfigEntry(
        domain="fluss",
        data={"api_key": "test_api_key"},
    )
    entry.add_to_hass(hass)

    with patch(
        "fluss_api.main.FlussApiClient",
        return_value=mock_api_client,
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("button.test_device")
    assert state is None