"""Tests for the EnergyID integration init."""

import datetime as dt
from unittest.mock import MagicMock, call, patch

from aiohttp import ClientError
from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.energyid import (
    DEFAULT_UPLOAD_INTERVAL_SECONDS,
    EnergyIDRuntimeData,
    _async_handle_state_change,
    async_setup_entry,
    async_update_listeners,
)
from homeassistant.components.energyid.const import (
    CONF_ENERGYID_KEY,
    CONF_HA_ENTITY_ID,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import STATE_UNAVAILABLE, STATE_UNKNOWN
from homeassistant.core import Event, HomeAssistant
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.entity_registry import EntityRegistry

from .conftest import MOCK_CONFIG_DATA, TEST_RECORD_NAME

from tests.common import MockConfigEntry


async def test_async_setup_entry_success_claimed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client_claimed: MagicMock,
) -> None:
    """Test successful setup of a claimed device."""
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.energyid.WebhookClient",
        return_value=mock_webhook_client_claimed,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.LOADED
    assert isinstance(mock_config_entry.runtime_data, EnergyIDRuntimeData)
    assert mock_config_entry.runtime_data.client == mock_webhook_client_claimed

    mock_webhook_client_claimed.authenticate.assert_called_once()
    mock_webhook_client_claimed.start_auto_sync.assert_called_once_with(
        interval_seconds=120
    )


async def test_async_setup_entry_no_upload_interval(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client_claimed: MagicMock,
) -> None:
    """Test setup uses default interval if policy is missing it."""
    mock_webhook_client_claimed.webhook_policy = {}
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.energyid.WebhookClient",
        return_value=mock_webhook_client_claimed,
    ):
        await async_setup_entry(hass, mock_config_entry)
        await hass.async_block_till_done()

    mock_webhook_client_claimed.start_auto_sync.assert_called_once_with(
        interval_seconds=DEFAULT_UPLOAD_INTERVAL_SECONDS
    )


@pytest.mark.parametrize(
    ("exception", "expected_state"),
    [
        (ClientError, ConfigEntryNotReady),
        (Exception, ConfigEntryNotReady),
    ],
)
async def test_async_setup_entry_auth_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    exception: Exception,
    expected_state: ConfigEntryState,
) -> None:
    """Test setup failure due to authentication errors."""
    mock_config_entry.add_to_hass(hass)
    mock_client = MagicMock()
    mock_client.authenticate.side_effect = exception("API Error")

    with patch(
        "homeassistant.components.energyid.WebhookClient", return_value=mock_client
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.SETUP_RETRY


async def test_async_setup_entry_not_claimed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client_unclaimed: MagicMock,
) -> None:
    """Test setup failure if device is not claimed."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.energyid.WebhookClient",
        return_value=mock_webhook_client_unclaimed,
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.SETUP_ERROR


async def test_async_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client_claimed: MagicMock,
) -> None:
    """Test successful unloading of a config entry."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.energyid.WebhookClient",
        return_value=mock_webhook_client_claimed,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.NOT_LOADED
    mock_webhook_client_claimed.close.assert_called_once()
    assert not hasattr(mock_config_entry, "runtime_data")


async def test_async_update_listeners(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the creation and update of state listeners."""
    now = dt.datetime(2024, 1, 1, 12, 0, 0, tzinfo=dt.UTC)
    freezer.move_to(now)

    entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG_DATA, title=TEST_RECORD_NAME
    )
    entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG_DATA, title=TEST_RECORD_NAME
    )
    entry.add_to_hass(hass)

    # --- Create mock entities and subentries ---
    entity_registry.async_get_or_create(
        "sensor", "test", "1", suggested_object_id="power"
    )
    hass.states.async_set("sensor.power", "100.5", {"last_updated": now})
    sub_entry_1 = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HA_ENTITY_ID: "sensor.power", CONF_ENERGYID_KEY: "pwr"},
    )
    entity_registry.async_get_or_create(
        "sensor", "test", "2", suggested_object_id="gas"
    )
    hass.states.async_set("sensor.gas", "50")
    sub_entry_2 = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HA_ENTITY_ID: "sensor.gas", CONF_ENERGYID_KEY: "gas"},
    )

    # Manually assign the subentries to the parent entry's subentries property.
    entry.subentries = {
        sub_entry_1.entry_id: sub_entry_1,
        sub_entry_2.entry_id: sub_entry_2,
    }

    mock_client = MagicMock()
    mock_sensor = MagicMock()
    mock_client.get_or_create_sensor.return_value = mock_sensor
    entry.runtime_data = EnergyIDRuntimeData(
        client=mock_client, listeners={}, mappings={}
    )

    with patch(
        "homeassistant.components.energyid.async_track_state_change_event"
    ) as mock_track:
        await async_update_listeners(hass, entry)

        mock_track.assert_called_once()
        assert set(mock_track.call_args[0][1]) == {"sensor.power", "sensor.gas"}
        assert entry.runtime_data.mappings == {
            "sensor.power": "pwr",
            "sensor.gas": "gas",
        }

    mock_client.get_or_create_sensor.assert_has_calls(
        [call("pwr"), call("gas")], any_order=True
    )
    # Both sensors have valid states, so update is called for each
    assert mock_sensor.update.call_count == 2
    mock_sensor.update.assert_any_call(100.5, now)
    mock_sensor.update.assert_any_call(50.0, now)


@pytest.mark.parametrize(
    ("state_val", "should_log_warning", "should_call_update"),
    [
        ("123.4", False, True),
        (STATE_UNKNOWN, False, False),
        (STATE_UNAVAILABLE, False, False),
        ("bad", True, False),
    ],
)
async def test_async_handle_state_change(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client_claimed: MagicMock,
    state_val: str,
    should_log_warning: bool,
    should_call_update: bool,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test the state change handler logic directly."""
    entity_id = "sensor.test"
    energyid_key = "test_key"

    # 1. Prepare the runtime data and attach it to the config entry
    mock_config_entry.runtime_data = EnergyIDRuntimeData(
        client=mock_webhook_client_claimed,
        listeners={},
        mappings={entity_id: energyid_key},
    )

    # 2. Make sure the entry is retrievable by hass.config_entries.async_get_entry
    # This is the crucial step that might have been missed.
    mock_config_entry.add_to_hass(hass)

    # 3. Create the event object
    now = dt.datetime.now(dt.UTC)
    mock_new_state = MagicMock()
    mock_new_state.state = state_val
    mock_new_state.last_updated = now

    event = Event(
        "state_changed",
        data={"entity_id": entity_id, "new_state": mock_new_state},
    )

    # 4. Call the function under test
    _async_handle_state_change(hass, mock_config_entry.entry_id, event)

    # 5. Assert the results
    mock_sensor_update = (
        mock_webhook_client_claimed.get_or_create_sensor.return_value.update
    )

    if should_call_update:
        mock_sensor_update.assert_called_once_with(float(state_val), now)
    else:
        mock_sensor_update.assert_not_called()

    assert ("Cannot convert state" in caplog.text) == should_log_warning
