"""Test sensor platform of Ping."""

from datetime import timedelta
from unittest.mock import patch

from freezegun.api import FrozenDateTimeFactory
from icmplib import Host, NameLookupError
import pytest
from pytest_homeassistant.common import async_fire_time_changed
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.const import STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "setup_integration")
@pytest.mark.parametrize(
    "sensor_name",
    [
        "round_trip_time_average",
        "round_trip_time_maximum",
        "round_trip_time_mean_deviation",  # should be None in the snapshot
        "round_trip_time_minimum",
        "jitter",
        "packet_loss",
    ],
)
async def test_setup_and_update(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
    sensor_name: str,
) -> None:
    """Test sensor setup and update."""

    entry = entity_registry.async_get(f"sensor.10_10_10_10_{sensor_name}")
    assert entry == snapshot(exclude=props("unique_id"))

    state = hass.states.get(f"sensor.10_10_10_10_{sensor_name}")
    assert state == snapshot


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "setup_integration")
async def test_host_unreachable(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory
) -> None:
    """Test packet loss reports 100% when no replies are received."""
    with patch(
        "homeassistant.components.ping.helpers.async_ping",
        return_value=Host(address="10.10.10.10", packets_sent=10, rtts=[]),
    ):
        freezer.tick(timedelta(minutes=6))
        await hass.async_block_till_done()

    assert hass.states.get("sensor.10_10_10_10_packet_loss").state == "100.0"
    assert (
        hass.states.get("sensor.10_10_10_10_round_trip_time_average").state
        == STATE_UNAVAILABLE
    )


@pytest.mark.usefixtures("entity_registry_enabled_by_default", "setup_integration")
async def test_name_lookup_error_and_recovery(
    hass: HomeAssistant, freezer: FrozenDateTimeFactory, patch_ping: Host
) -> None:
    """Test sensors become unavailable on a DNS failure and recover after."""
    with patch(
        "homeassistant.components.ping.helpers.async_ping",
        side_effect=NameLookupError("10.10.10.10"),
    ):
        freezer.tick(timedelta(minutes=6))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    for sensor in ("packet_loss", "round_trip_time_average", "jitter"):
        assert hass.states.get(f"sensor.10_10_10_10_{sensor}").state == (
            STATE_UNAVAILABLE
        )

    freezer.tick(timedelta(minutes=6))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    for sensor in ("packet_loss", "round_trip_time_average", "jitter"):
        assert hass.states.get(f"sensor.10_10_10_10_{sensor}").state != (
            STATE_UNAVAILABLE
        )
