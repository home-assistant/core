"""Test the victron_gx init."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from victron_mqtt import AuthenticationError, CannotConnectError, MetricKind

from homeassistant.components.victron_gx.config_flow import DEFAULT_PORT
from homeassistant.components.victron_gx.const import CONF_INSTALLATION_ID, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

MOCK_INSTALLATION_ID = "d41243d9b9c6"
MOCK_HOST = "192.168.1.100"


@pytest.fixture
def mock_victron_hub_library():
    """Mock the victron_mqtt library."""
    with patch("homeassistant.components.victron_gx.hub.VictronVenusHub") as mock_lib:
        hub_instance = MagicMock()
        hub_instance.connect = AsyncMock()
        hub_instance.disconnect = AsyncMock()
        hub_instance.installation_id = MOCK_INSTALLATION_ID
        mock_lib.return_value = hub_instance
        yield mock_lib


@pytest.mark.usefixtures("mock_victron_hub_library")
async def test_setup_entry(hass: HomeAssistant) -> None:
    """Test setup entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_SSL: False,
            CONF_INSTALLATION_ID: MOCK_INSTALLATION_ID,
        },
        unique_id=MOCK_INSTALLATION_ID,
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED


@pytest.mark.usefixtures("mock_victron_hub_library")
async def test_unload_entry(hass: HomeAssistant) -> None:
    """Test unload entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_SSL: False,
            CONF_INSTALLATION_ID: MOCK_INSTALLATION_ID,
        },
        unique_id=MOCK_INSTALLATION_ID,
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("mock_victron_hub_library")
async def test_unload_entry_does_not_cleanup_on_platform_unload_failure(
    hass: HomeAssistant,
) -> None:
    """Test unload failure does not stop hub or clear callbacks."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_SSL: False,
            CONF_INSTALLATION_ID: MOCK_INSTALLATION_ID,
        },
        unique_id=MOCK_INSTALLATION_ID,
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    config_entry.runtime_data.new_metric_callbacks[MetricKind.SENSOR] = MagicMock()
    hub_disconnect = config_entry.runtime_data._hub.disconnect

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        return_value=False,
    ):
        assert not await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.FAILED_UNLOAD
    assert config_entry.runtime_data.new_metric_callbacks
    hub_disconnect.assert_not_awaited()


@pytest.mark.usefixtures("mock_victron_hub_library")
async def test_stop_on_homeassistant_stop(hass: HomeAssistant) -> None:
    """Test hub stops when Home Assistant stops."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_SSL: False,
            CONF_INSTALLATION_ID: MOCK_INSTALLATION_ID,
        },
        unique_id=MOCK_INSTALLATION_ID,
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    hub_disconnect = config_entry.runtime_data._hub.disconnect
    hub_disconnect.assert_not_awaited()

    # Fire the stop event
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    hub_disconnect.assert_awaited_once()


@pytest.mark.parametrize(
    ("connect_exception", "expected_state"),
    [
        (CannotConnectError("Connection failed"), ConfigEntryState.SETUP_RETRY),
        (AuthenticationError("Auth failed"), ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_setup_entry_start_failure_unloads_platforms_and_callbacks(
    hass: HomeAssistant,
    connect_exception: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test setup cleanup when hub start fails after platform forwarding."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_SSL: False,
            CONF_INSTALLATION_ID: MOCK_INSTALLATION_ID,
        },
        unique_id=MOCK_INSTALLATION_ID,
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.victron_gx.hub.VictronVenusHub.connect",
        side_effect=connect_exception,
    ):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is expected_state
    assert config_entry.runtime_data.new_metric_callbacks == {}


async def test_hub_start_connection_error(
    hass: HomeAssistant,
) -> None:
    """Test hub start with connection error."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: MOCK_HOST,
            CONF_PORT: DEFAULT_PORT,
            CONF_SSL: False,
            CONF_INSTALLATION_ID: MOCK_INSTALLATION_ID,
        },
        unique_id=MOCK_INSTALLATION_ID,
    )
    config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.victron_gx.hub.VictronVenusHub.connect",
        side_effect=CannotConnectError("Connection failed"),
    ):
        # Attempt to set up the config entry - should fail and mark as SETUP_RETRY
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        # Verify the config entry is in SETUP_RETRY state (not loaded due to error)
        assert config_entry.state is ConfigEntryState.SETUP_RETRY
