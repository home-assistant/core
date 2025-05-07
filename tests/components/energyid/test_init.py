"""Tests for the EnergyID integration init."""

import datetime as dt
import functools
from unittest.mock import AsyncMock, MagicMock, Mock, patch

from freezegun.api import FrozenDateTimeFactory
import pytest

from homeassistant.components.energyid import (
    _async_handle_state_change,
    async_update_listeners,
    # LISTENER_TYPE_* constants are internal to __init__.py
)
from homeassistant.components.energyid.const import (
    CONF_ENERGYID_KEY,
    CONF_HA_ENTITY_ID,
    DATA_CLIENT,
    DATA_LISTENERS,
    DATA_MAPPINGS,
    DEFAULT_UPLOAD_INTERVAL_SECONDS,
    DOMAIN,
)
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import (
    EVENT_HOMEASSISTANT_STOP,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import Event, HomeAssistant, State
from homeassistant.helpers import entity_registry as er

from .conftest import (
    MOCK_CONFIG_DATA,
    MOCK_OPTIONS_DATA,
    TEST_DEVICE_NAME as CONTEXT_TEST_DEVICE_NAME,
    TEST_ENERGYID_KEY,
    TEST_HA_ENTITY_ID,
)

from tests.common import MockConfigEntry


async def test_async_setup_entry_success_claimed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test successful setup of a claimed device."""
    mock_config_entry.add_to_hass(hass)

    # --- FIX: Patch where the function is *used* ---
    with (
        patch(
            "homeassistant.components.energyid.WebhookClient",
            return_value=mock_webhook_client,
        ),
        patch(
            "homeassistant.components.energyid.async_track_state_change_event"
        ) as mock_track_event,
    ):
        # --- End Fix ---
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        if mock_config_entry.options:
            mock_track_event.assert_called_once()
        else:
            mock_track_event.assert_not_called()

    assert mock_config_entry.state == ConfigEntryState.LOADED
    assert DOMAIN in hass.data
    assert mock_config_entry.entry_id in hass.data[DOMAIN]
    assert (
        hass.data[DOMAIN][mock_config_entry.entry_id][DATA_CLIENT]
        == mock_webhook_client
    )

    mock_webhook_client.authenticate.assert_called_once()
    mock_webhook_client.start_auto_sync.assert_called_once_with(
        interval_seconds=mock_webhook_client.webhook_policy.get("uploadInterval")
    )

    listeners_dict = hass.data[DOMAIN][mock_config_entry.entry_id][DATA_LISTENERS]
    assert (
        listeners_dict.get("stop_listener") is not None
    )  # Using key defined in __init__.py
    if mock_config_entry.options:
        assert (
            listeners_dict.get("state_listener") is not None
        )  # Using key defined in __init__.py
    else:
        assert listeners_dict.get("state_listener") is None

    ent_reg_helper = er.async_get(hass)
    expected_entity_id_base = mock_config_entry.title.lower().replace(" ", "_")
    entity_id = ent_reg_helper.async_get_entity_id(
        "sensor", DOMAIN, f"{mock_config_entry.entry_id}_status"
    )
    assert entity_id == f"sensor.{expected_entity_id_base}_status"


async def test_async_setup_entry_success_unclaimed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test successful setup of an unclaimed device."""
    mock_config_entry.add_to_hass(hass)
    unclaimed_client = MagicMock()
    unclaimed_client.authenticate = AsyncMock(return_value=False)
    unclaimed_client.is_claimed = False
    unclaimed_client.close = AsyncMock()
    unclaimed_client.start_auto_sync = MagicMock()
    unclaimed_client.webhook_policy = {}
    unclaimed_client.device_name = CONTEXT_TEST_DEVICE_NAME

    # --- FIX: Patch where the function is *used* ---
    with (
        patch(
            "homeassistant.components.energyid.WebhookClient",
            return_value=unclaimed_client,
        ),
        patch(
            "homeassistant.components.energyid.async_track_state_change_event"
        ) as mock_track_event_unclaimed,
    ):
        # --- End Fix ---
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        if mock_config_entry.options:
            mock_track_event_unclaimed.assert_called_once()
        else:
            mock_track_event_unclaimed.assert_not_called()

    assert mock_config_entry.state == ConfigEntryState.LOADED
    unclaimed_client.authenticate.assert_called_once()
    unclaimed_client.start_auto_sync.assert_not_called()
    assert f"EnergyID device '{CONTEXT_TEST_DEVICE_NAME}' is not claimed" in caplog.text

    listeners_dict = hass.data[DOMAIN][mock_config_entry.entry_id][DATA_LISTENERS]
    assert listeners_dict.get("stop_listener") is not None
    if mock_config_entry.options:
        assert listeners_dict.get("state_listener") is not None
    else:
        assert listeners_dict.get("state_listener") is None


async def test_async_setup_entry_auth_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test setup failure due to authentication error."""
    mock_config_entry.add_to_hass(hass)
    mock_webhook_client.device_name = CONTEXT_TEST_DEVICE_NAME
    mock_webhook_client.authenticate = AsyncMock(side_effect=RuntimeError("API Error"))

    with patch(
        "homeassistant.components.energyid.WebhookClient",
        return_value=mock_webhook_client,
    ):
        assert not await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.SETUP_RETRY
    assert (
        f"Failed to authenticate EnergyID for {CONTEXT_TEST_DEVICE_NAME}: API Error"
        in caplog.text
    )


async def test_async_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test successful unloading of a config entry."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.energyid.WebhookClient",
        return_value=mock_webhook_client,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    assert mock_config_entry.entry_id in hass.data[DOMAIN]

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state == ConfigEntryState.NOT_LOADED
    mock_webhook_client.close.assert_called_once()
    assert mock_config_entry.entry_id not in hass.data.get(DOMAIN, {})


async def test_home_assistant_stop_event(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test client is closed on Home Assistant stop event."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.energyid.WebhookClient",
        return_value=mock_webhook_client,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    original_close_call_count = mock_webhook_client.close.call_count
    hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
    await hass.async_block_till_done()

    assert mock_webhook_client.close.call_count > original_close_call_count


async def test_config_entry_update_listener(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test the config entry update listener reloads listeners."""
    mock_config_entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.energyid.WebhookClient",
            return_value=mock_webhook_client,
        ),
        patch(
            "homeassistant.components.energyid.async_update_listeners"
        ) as mock_update_listeners,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        mock_update_listeners.reset_mock()

        hass.config_entries.async_update_entry(
            mock_config_entry, options={"new_option": "value"}
        )
        await hass.async_block_till_done()

        mock_update_listeners.assert_called_once_with(hass, mock_config_entry)


async def test_async_update_listeners_no_options(
    hass: HomeAssistant,
    mock_webhook_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test async_update_listeners with no options."""
    entry_no_opts = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG_DATA,
        options={},
        entry_id="test_entry_no_options",
        title=CONTEXT_TEST_DEVICE_NAME,
    )
    entry_no_opts.add_to_hass(hass)
    mock_webhook_client.device_name = CONTEXT_TEST_DEVICE_NAME

    # --- FIX: Patch where the function is *used* ---
    with (
        patch(
            "homeassistant.components.energyid.WebhookClient",
            return_value=mock_webhook_client,
        ),
        patch(
            "homeassistant.components.energyid.async_track_state_change_event"
        ) as mock_track_event,
    ):
        # --- End Fix ---
        assert await hass.config_entries.async_setup(entry_no_opts.entry_id)
        await hass.async_block_till_done()
        mock_track_event.assert_not_called()

    assert (
        f"No entities configured for EnergyID device '{CONTEXT_TEST_DEVICE_NAME}'"
        in caplog.text
    )
    listeners = hass.data[DOMAIN][entry_no_opts.entry_id][DATA_LISTENERS]
    assert listeners.get("stop_listener") is not None
    assert listeners.get("state_listener") is None
    assert hass.data[DOMAIN][entry_no_opts.entry_id][DATA_MAPPINGS] == {}


async def test_async_update_listeners_with_options(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test async_update_listeners correctly sets up tracking."""
    mock_config_entry.add_to_hass(hass)
    mock_webhook_client.device_name = CONTEXT_TEST_DEVICE_NAME

    # --- FIX: Patch where the function is *used* ---
    with (
        patch(
            "homeassistant.components.energyid.WebhookClient",
            return_value=mock_webhook_client,
        ),
        patch(
            "homeassistant.components.energyid.async_track_state_change_event"
        ) as mock_track_event,
    ):
        # --- End Fix ---
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        mock_track_event.assert_called_once()
        tracked_entities = mock_track_event.call_args[0][1]
        assert tracked_entities == [TEST_HA_ENTITY_ID]
        assert isinstance(mock_track_event.call_args[0][2], functools.partial)

        assert hass.data[DOMAIN][mock_config_entry.entry_id][DATA_MAPPINGS] == {
            TEST_HA_ENTITY_ID: TEST_ENERGYID_KEY
        }
        mock_webhook_client.get_or_create_sensor.assert_called_with(TEST_ENERGYID_KEY)
        listeners = hass.data[DOMAIN][mock_config_entry.entry_id][DATA_LISTENERS]
        assert listeners.get("stop_listener") is not None
        assert listeners.get("state_listener") is not None


async def test_async_update_listeners_invalid_options(
    hass: HomeAssistant,
    mock_webhook_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test async_update_listeners skips invalid options."""
    invalid_options = {
        "valid_mapping": MOCK_OPTIONS_DATA[TEST_HA_ENTITY_ID],
        "invalid_non_dict": "not_a_dict",
        "invalid_missing_key": {CONF_HA_ENTITY_ID: "sensor.another"},
        "invalid_wrong_type": {CONF_HA_ENTITY_ID: 123, CONF_ENERGYID_KEY: "key"},
    }
    entry_invalid_opts = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG_DATA,
        options=invalid_options,
        entry_id="test_entry_invalid_opts",
        title=CONTEXT_TEST_DEVICE_NAME,
    )
    entry_invalid_opts.add_to_hass(hass)
    mock_webhook_client.device_name = CONTEXT_TEST_DEVICE_NAME

    # --- FIX: Patch where the function is *used* ---
    with (
        patch(
            "homeassistant.components.energyid.WebhookClient",
            return_value=mock_webhook_client,
        ),
        patch(
            "homeassistant.components.energyid.async_track_state_change_event"
        ) as mock_track_event,
    ):
        # --- End Fix ---
        assert await hass.config_entries.async_setup(entry_invalid_opts.entry_id)
        await hass.async_block_till_done()

        mock_track_event.assert_called_once()
        tracked_entities = mock_track_event.call_args[0][1]
        assert tracked_entities == [TEST_HA_ENTITY_ID]

    assert "Skipping non-dictionary options item: not_a_dict" in caplog.text
    assert (
        "Skipping invalid mapping data: {'ha_entity_id': 'sensor.another'}"
        in caplog.text
    )
    assert (
        "Skipping invalid mapping data: {'ha_entity_id': 123, 'energyid_key': 'key'}"
        in caplog.text
    )
    assert hass.data[DOMAIN][entry_invalid_opts.entry_id][DATA_MAPPINGS] == {
        TEST_HA_ENTITY_ID: TEST_ENERGYID_KEY
    }
    listeners = hass.data[DOMAIN][entry_invalid_opts.entry_id][DATA_LISTENERS]
    assert listeners.get("stop_listener") is not None
    assert listeners.get("state_listener") is not None


async def test_async_handle_state_change_success(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test successful state change handling."""
    now = dt.datetime(2023, 1, 1, 12, 0, 0, tzinfo=dt.UTC)
    freezer.move_to(now)

    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.energyid.WebhookClient",
        return_value=mock_webhook_client,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    hass.states.async_set(
        TEST_HA_ENTITY_ID, "10.0", {"last_updated": now - dt.timedelta(seconds=10)}
    )
    await hass.async_block_till_done()
    mock_webhook_client.update_sensor.reset_mock()

    new_state = State(TEST_HA_ENTITY_ID, "12.5", last_updated=now)
    event_data = {
        "entity_id": TEST_HA_ENTITY_ID,
        "old_state": hass.states.get(TEST_HA_ENTITY_ID),
        "new_state": new_state,
    }
    mock_event = Event("state_changed", data=event_data)

    _async_handle_state_change(hass, mock_config_entry.entry_id, mock_event)
    await hass.async_block_till_done()

    mock_webhook_client.update_sensor.assert_called_once_with(
        TEST_ENERGYID_KEY, 12.5, now
    )


@pytest.mark.parametrize(
    "bad_state_value", [STATE_UNKNOWN, STATE_UNAVAILABLE, "not_a_float"]
)
async def test_async_handle_state_change_invalid_states(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
    bad_state_value: str,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test state change handling for invalid states."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.energyid.WebhookClient",
        return_value=mock_webhook_client,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    hass.states.async_set(TEST_HA_ENTITY_ID, "0.0")
    await hass.async_block_till_done()
    mock_webhook_client.update_sensor.reset_mock()

    new_state = State(TEST_HA_ENTITY_ID, bad_state_value)
    event_data = {"entity_id": TEST_HA_ENTITY_ID, "new_state": new_state}
    mock_event = Event("state_changed", data=event_data)

    _async_handle_state_change(hass, mock_config_entry.entry_id, mock_event)
    await hass.async_block_till_done()

    mock_webhook_client.update_sensor.assert_not_called()
    if bad_state_value == "not_a_float":
        assert (
            f"Cannot convert state '{bad_state_value}' of {TEST_HA_ENTITY_ID} to float"
            in caplog.text
        )


async def test_async_handle_state_change_missing_data(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test state change handling with missing entity_id or new_state."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.energyid.WebhookClient",
        return_value=mock_webhook_client,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    hass.states.async_set(TEST_HA_ENTITY_ID, "0.0")
    await hass.async_block_till_done()
    mock_webhook_client.update_sensor.reset_mock()

    event_data_no_entity = {"new_state": State(TEST_HA_ENTITY_ID, "10.0")}
    _async_handle_state_change(
        hass,
        mock_config_entry.entry_id,
        Event("state_changed", data=event_data_no_entity),
    )
    await hass.async_block_till_done()
    mock_webhook_client.update_sensor.assert_not_called()

    event_data_no_state = {"entity_id": TEST_HA_ENTITY_ID}
    _async_handle_state_change(
        hass,
        mock_config_entry.entry_id,
        Event("state_changed", data=event_data_no_state),
    )
    await hass.async_block_till_done()
    mock_webhook_client.update_sensor.assert_not_called()


async def test_async_handle_state_change_no_mapping(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test state change for an entity not in mappings."""
    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.energyid.WebhookClient",
        return_value=mock_webhook_client,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    hass.states.async_set(TEST_HA_ENTITY_ID, "0.0")
    await hass.async_block_till_done()
    mock_webhook_client.update_sensor.reset_mock()

    unmapped_entity_id = "sensor.unmapped"
    hass.states.async_set(unmapped_entity_id, "10.0")

    new_state = State(unmapped_entity_id, "20.0")
    event_data = {"entity_id": unmapped_entity_id, "new_state": new_state}

    _async_handle_state_change(
        hass, mock_config_entry.entry_id, Event("state_changed", data=event_data)
    )
    await hass.async_block_till_done()

    mock_webhook_client.update_sensor.assert_not_called()


async def test_async_handle_state_change_integration_data_missing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test state change when integration data is missing (e.g., during unload)."""
    mock_config_entry.add_to_hass(hass)

    hass.data.setdefault(DOMAIN, {})
    if mock_config_entry.entry_id in hass.data[DOMAIN]:
        del hass.data[DOMAIN][mock_config_entry.entry_id]

    new_state = State(TEST_HA_ENTITY_ID, "25.0")
    event_data = {"entity_id": TEST_HA_ENTITY_ID, "new_state": new_state}

    _async_handle_state_change(
        hass, mock_config_entry.entry_id, Event("state_changed", data=event_data)
    )
    await hass.async_block_till_done()

    assert (
        f"Integration data not found for entry {mock_config_entry.entry_id} during state change for {TEST_HA_ENTITY_ID}"
        in caplog.text
    )


async def test_async_update_listeners_integration_data_missing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test async_update_listeners when integration data is unexpectedly missing."""
    mock_config_entry.add_to_hass(hass)

    hass.data.setdefault(DOMAIN, {})
    if mock_config_entry.entry_id in hass.data[DOMAIN]:
        del hass.data[DOMAIN][mock_config_entry.entry_id]

    await async_update_listeners(hass, mock_config_entry)

    assert (
        f"Integration data missing for {mock_config_entry.entry_id} during listener update"
        in caplog.text
    )


async def test_async_setup_entry_default_upload_interval(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
) -> None:
    """Test setup uses default upload interval if not in policy."""
    mock_webhook_client.webhook_policy = {}
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.energyid.WebhookClient",
        return_value=mock_webhook_client,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    mock_webhook_client.start_auto_sync.assert_called_once_with(
        interval_seconds=DEFAULT_UPLOAD_INTERVAL_SECONDS
    )


async def test_async_handle_state_change_timestamp_handling(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test timestamp handling in _async_handle_state_change."""
    now_utc = dt.datetime(2023, 1, 1, 12, 0, 0, tzinfo=dt.UTC)
    now_naive = dt.datetime(2023, 1, 1, 12, 0, 0)
    now_local_tz = dt.datetime(
        2023, 1, 1, 12, 0, 0, tzinfo=dt.timezone(dt.timedelta(hours=2))
    )

    freezer.move_to(now_utc)

    mock_config_entry.add_to_hass(hass)
    with patch(
        "homeassistant.components.energyid.WebhookClient",
        return_value=mock_webhook_client,
    ):
        assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    hass.states.async_set(TEST_HA_ENTITY_ID, "initial_value")
    await hass.async_block_till_done()
    mock_webhook_client.update_sensor.reset_mock()

    # Case 1: Timestamp is already UTC
    state_utc = State(TEST_HA_ENTITY_ID, "1.0", last_updated=now_utc)
    _async_handle_state_change(
        hass,
        mock_config_entry.entry_id,
        Event(
            "state_changed",
            data={"entity_id": TEST_HA_ENTITY_ID, "new_state": state_utc},
        ),
    )
    await hass.async_block_till_done()
    mock_webhook_client.update_sensor.assert_called_once_with(
        TEST_ENERGYID_KEY, 1.0, now_utc
    )
    mock_webhook_client.update_sensor.reset_mock()

    # Case 2: Timestamp is naive
    state_naive = State(TEST_HA_ENTITY_ID, "2.0", last_updated=now_naive)
    _async_handle_state_change(
        hass,
        mock_config_entry.entry_id,
        Event(
            "state_changed",
            data={"entity_id": TEST_HA_ENTITY_ID, "new_state": state_naive},
        ),
    )
    await hass.async_block_till_done()
    mock_webhook_client.update_sensor.assert_called_once_with(
        TEST_ENERGYID_KEY, 2.0, now_naive.replace(tzinfo=dt.UTC)
    )
    mock_webhook_client.update_sensor.reset_mock()

    # Case 3: Timestamp has a non-UTC timezone
    state_local_tz = State(TEST_HA_ENTITY_ID, "3.0", last_updated=now_local_tz)
    _async_handle_state_change(
        hass,
        mock_config_entry.entry_id,
        Event(
            "state_changed",
            data={"entity_id": TEST_HA_ENTITY_ID, "new_state": state_local_tz},
        ),
    )
    await hass.async_block_till_done()
    mock_webhook_client.update_sensor.assert_called_once_with(
        TEST_ENERGYID_KEY, 3.0, now_local_tz.astimezone(dt.UTC)
    )
    mock_webhook_client.update_sensor.reset_mock()

    # Case 4: Timestamp is not a datetime object
    mock_state_invalid_ts = Mock(spec=State)
    mock_state_invalid_ts.state = "4.0"
    mock_state_invalid_ts.last_updated = "this_is_a_string"
    mock_state_invalid_ts.entity_id = TEST_HA_ENTITY_ID
    mock_state_invalid_ts.attributes = {}

    with patch(
        "homeassistant.components.energyid._LOGGER.warning"
    ) as mock_logger_warning:
        _async_handle_state_change(
            hass,
            mock_config_entry.entry_id,
            Event(
                "state_changed",
                data={
                    "entity_id": TEST_HA_ENTITY_ID,
                    "new_state": mock_state_invalid_ts,
                },
            ),
        )
        await hass.async_block_till_done()
        mock_webhook_client.update_sensor.assert_called_once_with(
            TEST_ENERGYID_KEY, 4.0, now_utc
        )
        mock_logger_warning.assert_called_once_with(
            "Invalid timestamp type (%s) for %s, using current UTC time",
            "str",
            TEST_HA_ENTITY_ID,
        )
