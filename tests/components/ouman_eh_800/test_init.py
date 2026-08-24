"""Test the Ouman EH-800 setup."""

from datetime import timedelta
from unittest.mock import AsyncMock

from freezegun.api import FrozenDateTimeFactory
from ouman_eh_800_api import (
    OumanClientAuthenticationError,
    OumanClientCommunicationError,
)
import pytest

from homeassistant.components.ouman_eh_800.const import (
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DOMAIN,
    OumanDevice,
)
from homeassistant.components.select import (
    ATTR_OPTION,
    DOMAIN as SELECT_DOMAIN,
    SERVICE_SELECT_OPTION,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.usefixtures("mock_ouman_client")
async def test_sub_devices_link_to_main_device(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test that the L1/L2 sub-devices link to the main device via via_device_id."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)

    entry_id = mock_config_entry.entry_id
    main_device = device_registry.async_get_device_by_identifier(
        (DOMAIN, entry_id), config_entry_id=entry_id
    )
    assert main_device is not None

    for sub_device in (OumanDevice.L1, OumanDevice.L2):
        device = device_registry.async_get_device_by_identifier(
            (DOMAIN, f"{entry_id}_{sub_device}"), config_entry_id=entry_id
        )
        assert device is not None
        assert device.via_device_id == main_device.id


@pytest.mark.usefixtures("mock_ouman_client")
async def test_setup_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test config entry setup and unload."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("error", "expected_state", "expected_reauth_flows"),
    [
        pytest.param(
            OumanClientCommunicationError("Connection failed"),
            ConfigEntryState.SETUP_RETRY,
            0,
            id="communication_error",
        ),
        pytest.param(
            OumanClientAuthenticationError("Invalid credentials"),
            ConfigEntryState.SETUP_ERROR,
            1,
            id="authentication_error",
        ),
    ],
)
async def test_setup_error(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_ouman_client: AsyncMock,
    error: Exception,
    expected_state: ConfigEntryState,
    expected_reauth_flows: int,
) -> None:
    """Test that setup raises the correct config-entry exception on client errors."""
    mock_ouman_client.login.side_effect = error
    mock_config_entry.add_to_hass(hass)

    assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert mock_config_entry.state is expected_state

    reauth_flows = hass.config_entries.flow.async_progress_by_handler(
        DOMAIN, match_context={"source": SOURCE_REAUTH}
    )
    assert len(reauth_flows) == expected_reauth_flows


@pytest.mark.usefixtures("init_integration")
async def test_update_failed(
    hass: HomeAssistant,
    mock_ouman_client: AsyncMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that entities become unavailable when a data update fails."""
    entity_id = "sensor.ouman_eh_800_outside_temperature"
    assert hass.states.get(entity_id).state == "0.4"

    mock_ouman_client.get_values.side_effect = OumanClientCommunicationError(
        "Timeout connecting to device"
    )
    freezer.tick(timedelta(seconds=DEFAULT_SCAN_INTERVAL_SECONDS))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    assert hass.states.get(entity_id).state == STATE_UNAVAILABLE


@pytest.mark.parametrize("init_integration", [Platform.SELECT], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_reauth_started_on_action_auth_failure(
    hass: HomeAssistant,
    mock_ouman_client: AsyncMock,
) -> None:
    """Test that an auth failure when setting a value starts a reauth flow.

    All platforms set values through the same coordinator method, which
    reloads the config entry on an authentication failure; setup then
    re-validates the credentials and starts the reauth flow. The select
    entity here is just one arbitrary way to trigger that shared path.
    """
    error = OumanClientAuthenticationError("Wrong username or password")
    mock_ouman_client.set_endpoint_value.side_effect = error
    mock_ouman_client.login.side_effect = error

    with pytest.raises(HomeAssistantError, match="Authentication failed"):
        await hass.services.async_call(
            SELECT_DOMAIN,
            SERVICE_SELECT_OPTION,
            {
                ATTR_ENTITY_ID: "select.ouman_eh_800_home_away_mode",
                ATTR_OPTION: "away",
            },
            blocking=True,
        )

    await hass.async_block_till_done()
    reauth_flows = hass.config_entries.flow.async_progress_by_handler(
        DOMAIN, match_context={"source": SOURCE_REAUTH}
    )
    assert len(reauth_flows) == 1
