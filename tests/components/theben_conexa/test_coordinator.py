"""Tests for the Theben Conexa coordinator."""

from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from homeassistant.components.theben_conexa.const import DOMAIN, MAX_MEASUREMENT_AGE
from homeassistant.components.theben_conexa.coordinator import SmgwSensorCoordinator
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry


async def __testScheduled(
    hass: HomeAssistant, coordinator: SmgwSensorCoordinator, age: int
):
    now = dt_util.utcnow()
    data_timestamp = now - timedelta(seconds=age)
    values = {"meter": SimpleNamespace(utcTimestamp=data_timestamp.isoformat())}

    cancel_callback = Mock()
    coordinator._api.getLatestValues = AsyncMock(return_value=values)
    last_unscheduled = coordinator._unscheduled_updates
    with (
        patch(
            "homeassistant.components.theben_conexa.coordinator.dt_util.utcnow",
            return_value=now,
        ),
        patch(
            "homeassistant.components.theben_conexa.coordinator.async_track_point_in_utc_time",
            return_value=cancel_callback,
        ) as mock_track,
    ):
        await coordinator._scheduled_update(now)

    coordinator._api.getLatestValues.assert_awaited_once()

    # Scheduled update always cancels pending unscheduled
    if last_unscheduled:
        last_unscheduled.assert_called_once()
        if coordinator._retries:
            assert coordinator._unscheduled_updates is not last_unscheduled
        else:
            assert coordinator._unscheduled_updates is None

    assert coordinator.data == values
    if age <= MAX_MEASUREMENT_AGE:
        assert coordinator._retries == 0
    elif coordinator._retries:
        assert coordinator._unscheduled_updates is cancel_callback
        mock_track.assert_called_once_with(
            hass,
            coordinator._unscheduled_update,
            now + timedelta(seconds=60),
        )
    else:
        assert coordinator._retries == 0


async def __testUnscheduled(
    hass: HomeAssistant, coordinator: SmgwSensorCoordinator, age: int
):
    now = dt_util.utcnow()
    data_timestamp = now - timedelta(seconds=age)
    values = {"meter": SimpleNamespace(utcTimestamp=data_timestamp.isoformat())}

    cancel_callback = Mock()
    coordinator._api.getLatestValues = AsyncMock(return_value=values)
    last_unscheduled = coordinator._unscheduled_updates
    with (
        patch(
            "homeassistant.components.theben_conexa.coordinator.dt_util.utcnow",
            return_value=now,
        ),
        patch(
            "homeassistant.components.theben_conexa.coordinator.async_track_point_in_utc_time",
            return_value=cancel_callback,
        ) as mock_track,
    ):
        await coordinator._unscheduled_update(now)

    coordinator._api.getLatestValues.assert_awaited_once()

    assert coordinator.data == values
    if age <= MAX_MEASUREMENT_AGE:
        assert coordinator._retries == 0
    elif coordinator._retries:
        assert coordinator._unscheduled_updates is cancel_callback
        mock_track.assert_called_once_with(
            hass,
            coordinator._unscheduled_update,
            now + timedelta(seconds=60),
        )
    else:
        assert coordinator._retries == 0
        assert coordinator._unscheduled_updates is None
        last_unscheduled.assert_called_once()


async def test_async_update_data_retries_when_data_is_old(
    hass: HomeAssistant,
) -> None:
    """Test the coordinator schedules a retry when data is stale."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.1.1.1",
            CONF_USERNAME: "user",
            CONF_PASSWORD: "pass",
            "m2mUrl": "http://test.url",
        },
    )
    entry.add_to_hass(hass)

    coordinator = SmgwSensorCoordinator(hass, entry)
    coordinator.data = {"dummy": SimpleNamespace()}
    coordinator._api = Mock()

    # Check good data range
    await __testScheduled(hass, coordinator, 0)
    assert coordinator._retries == 0
    await __testScheduled(hass, coordinator, MAX_MEASUREMENT_AGE)
    assert coordinator._retries == 0
    # Now check stale data
    await __testScheduled(hass, coordinator, MAX_MEASUREMENT_AGE + 1)
    assert coordinator._retries == 1
    await __testScheduled(hass, coordinator, MAX_MEASUREMENT_AGE + 1)
    assert coordinator._retries == 2
    # Check that it gives up after the second retry
    await __testScheduled(hass, coordinator, MAX_MEASUREMENT_AGE + 1)
    assert coordinator._retries == 0
    assert coordinator._unscheduled_updates is None

    await __testScheduled(hass, coordinator, MAX_MEASUREMENT_AGE + 1)
    assert coordinator._retries == 1
    assert coordinator._unscheduled_updates is not None
    # Check another failing unscheduled
    await __testUnscheduled(hass, coordinator, MAX_MEASUREMENT_AGE + 1)
    assert coordinator._retries == 2
    assert coordinator._unscheduled_updates is not None
    # Now check a successful one
    await __testUnscheduled(hass, coordinator, MAX_MEASUREMENT_AGE)
    assert coordinator._retries == 0
