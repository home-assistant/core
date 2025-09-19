"""Test Blue Current Init Component."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from bluecurrent_api.exceptions import (
    BlueCurrentException,
    InvalidApiToken,
    RequestLimitReached,
    WebsocketError,
)
import pytest
from voluptuous import MultipleInvalid

from homeassistant.components.blue_current import (
    CHARGING_CARD_ID,
    DOMAIN,
    SERVICE_START_CHARGE_SESSION,
    async_setup_entry,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICE_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    IntegrationError,
    ServiceValidationError,
)
from homeassistant.helpers.device_registry import DeviceRegistry

from . import init_integration

from tests.common import MockConfigEntry


async def test_load_unload_entry(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test load and unload entry."""
    with (
        patch("homeassistant.components.blue_current.Client.validate_api_token"),
        patch("homeassistant.components.blue_current.Client.wait_for_charge_points"),
        patch("homeassistant.components.blue_current.Client.get_charge_cards"),
        patch("homeassistant.components.blue_current.Client.disconnect"),
        patch(
            "homeassistant.components.blue_current.Client.connect",
            lambda self, on_data, on_open: hass.loop.create_future(),
        ),
    ):
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.LOADED

        await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("api_error", "config_error"),
    [
        (InvalidApiToken, ConfigEntryAuthFailed),
        (BlueCurrentException, ConfigEntryNotReady),
    ],
)
async def test_config_exceptions(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    api_error: BlueCurrentException,
    config_error: IntegrationError,
) -> None:
    """Test if the correct config error is raised when connecting to the api fails."""
    config_entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.blue_current.Client.validate_api_token",
            side_effect=api_error,
        ),
        pytest.raises(config_error),
    ):
        await async_setup_entry(hass, config_entry)


async def test_connect_websocket_error(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test reconnect when connect throws a WebsocketError."""

    with patch("homeassistant.components.blue_current.DELAY", 0):
        mock_client, started_loop, future_container = await init_integration(
            hass, config_entry
        )
        future_container.future.set_exception(WebsocketError)

        await started_loop.wait()
        assert mock_client.connect.call_count == 2


async def test_connect_request_limit_reached_error(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test reconnect when connect throws a RequestLimitReached."""

    mock_client, started_loop, future_container = await init_integration(
        hass, config_entry
    )
    future_container.future.set_exception(RequestLimitReached)
    mock_client.get_next_reset_delta.return_value = timedelta(seconds=0)

    await started_loop.wait()
    assert mock_client.get_next_reset_delta.call_count == 1
    assert mock_client.connect.call_count == 2


async def test_start_charging_action(
    hass: HomeAssistant, config_entry: MockConfigEntry, device_registry: DeviceRegistry
) -> None:
    """Test the start charing action when a charging card is provided."""
    integration = await init_integration(hass, config_entry, Platform.BUTTON)
    client = integration[0]

    await hass.services.async_call(
        DOMAIN,
        SERVICE_START_CHARGE_SESSION,
        {
            CONF_DEVICE_ID: list(device_registry.devices)[0],
            CHARGING_CARD_ID: "TEST_CARD",
        },
        blocking=True,
    )

    client.start_session.assert_called_once_with("101", "TEST_CARD")


async def test_start_charging_action_without_card(
    hass: HomeAssistant, config_entry: MockConfigEntry, device_registry: DeviceRegistry
) -> None:
    """Test the start charing action when no charging card is provided."""
    integration = await init_integration(hass, config_entry, Platform.BUTTON)
    client = integration[0]

    await hass.services.async_call(
        DOMAIN,
        SERVICE_START_CHARGE_SESSION,
        {
            CONF_DEVICE_ID: list(device_registry.devices)[0],
        },
        blocking=True,
    )

    client.start_session.assert_called_once_with("101", "BCU-APP")


async def test_start_charging_action_errors(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: DeviceRegistry,
) -> None:
    """Test the start charing action errors."""
    await init_integration(hass, config_entry, Platform.BUTTON)

    with pytest.raises(MultipleInvalid):
        # No device id
        await hass.services.async_call(
            DOMAIN,
            SERVICE_START_CHARGE_SESSION,
            {},
            blocking=True,
        )

    with pytest.raises(ServiceValidationError):
        # Invalid device id
        await hass.services.async_call(
            DOMAIN,
            SERVICE_START_CHARGE_SESSION,
            {CONF_DEVICE_ID: "INVALID"},
            blocking=True,
        )

    # Test when the device is not connected to a valid blue_current config entry.
    get_entry_mock = MagicMock()
    get_entry_mock.state = ConfigEntryState.LOADED

    with (
        patch.object(
            hass.config_entries, "async_get_entry", return_value=get_entry_mock
        ),
        pytest.raises(ServiceValidationError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_START_CHARGE_SESSION,
            {
                CONF_DEVICE_ID: list(device_registry.devices)[0],
            },
            blocking=True,
        )

    # Test when the blue_current config entry is not loaded.
    get_entry_mock = MagicMock()
    get_entry_mock.domain = DOMAIN
    get_entry_mock.state = ConfigEntryState.NOT_LOADED

    with (
        patch.object(
            hass.config_entries, "async_get_entry", return_value=get_entry_mock
        ),
        pytest.raises(ServiceValidationError),
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_START_CHARGE_SESSION,
            {
                CONF_DEVICE_ID: list(device_registry.devices)[0],
            },
            blocking=True,
        )
