"""Test the victron_gx_mqtt init."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant.components.victron_gx_mqtt.config_flow import DEFAULT_PORT
from homeassistant.components.victron_gx_mqtt.const import CONF_INSTALLATION_ID, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ConfigEntryAuthFailed, ConfigEntryNotReady

from tests.common import MockConfigEntry

MOCK_INSTALLATION_ID = "d41243d9b9c6"
MOCK_HOST = "192.168.1.100"


@pytest.fixture
def mock_victron_hub_library():
    """Mock the victron_mqtt library."""
    with patch(
        "homeassistant.components.victron_gx_mqtt.hub.VictronVenusHub"
    ) as mock_lib:
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

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
        return_value=True,
    ) as mock_forward:
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    mock_forward.assert_called_once()


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

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
        return_value=True,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        return_value=True,
    ) as mock_unload:
        assert await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    mock_unload.assert_called_once()


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

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
        return_value=True,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    config_entry.runtime_data.new_metric_callbacks[object()] = MagicMock()
    hub_disconnect = config_entry.runtime_data._hub.disconnect

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
        return_value=False,
    ) as mock_unload:
        assert not await hass.config_entries.async_unload(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.FAILED_UNLOAD
    assert config_entry.runtime_data.new_metric_callbacks
    hub_disconnect.assert_not_awaited()
    mock_unload.assert_called_once()


@pytest.mark.usefixtures("mock_victron_hub_library")
async def test_update_entry_does_not_reload(hass: HomeAssistant) -> None:
    """Test generic config entry updates do not trigger reload."""
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

    with (
        patch(
            "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
            return_value=True,
        ),
        patch(
            "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
            return_value=True,
        ),
        patch("homeassistant.config_entries.ConfigEntries.async_reload") as mock_reload,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        # Generic config updates should not trigger reloads.
        hass.config_entries.async_update_entry(
            config_entry,
            data={
                CONF_HOST: MOCK_HOST,
                CONF_PORT: DEFAULT_PORT,
                CONF_SSL: False,
                CONF_INSTALLATION_ID: MOCK_INSTALLATION_ID,
            },
        )
        await hass.async_block_till_done()

        # Verify no reload is triggered by a generic entry update.
        assert mock_reload.call_count == 0


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

    with patch(
        "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
        return_value=True,
    ):
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED
    hub_disconnect = config_entry.runtime_data._hub.disconnect
    hub_disconnect.assert_not_awaited()

    # Fire the stop event
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    hub_disconnect.assert_awaited_once()


@pytest.mark.usefixtures("mock_victron_hub_library")
@pytest.mark.parametrize(
    ("start_exception", "expected_state"),
    [
        (ConfigEntryNotReady, ConfigEntryState.SETUP_RETRY),
        (ConfigEntryAuthFailed, ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_setup_entry_start_failure_unloads_platforms_and_callbacks(
    hass: HomeAssistant,
    start_exception: Exception,
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

    async def _mock_forward(*_args, **_kwargs) -> None:
        config_entry.runtime_data.new_metric_callbacks[object()] = MagicMock()

    with (
        patch(
            "homeassistant.config_entries.ConfigEntries.async_forward_entry_setups",
            side_effect=_mock_forward,
        ) as mock_forward,
        patch(
            "homeassistant.config_entries.ConfigEntries.async_unload_platforms",
            return_value=True,
        ) as mock_unload,
        patch(
            "homeassistant.components.victron_gx_mqtt.Hub.start",
            side_effect=start_exception,
        ),
    ):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

    assert config_entry.state is expected_state
    assert config_entry.runtime_data.new_metric_callbacks == {}
    mock_forward.assert_called_once()
    mock_unload.assert_called_once()
