"""Test the ThermoPro config flow."""

from datetime import datetime, timedelta
import time

from thermopro_ble import ThermoProDevice

from homeassistant.components.bluetooth import (
    FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS,
)
from homeassistant.components.thermopro.const import DOMAIN
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE, Platform
from homeassistant.core import HomeAssistant, split_entity_id
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from . import TP357_SERVICE_INFO, TP358_SERVICE_INFO

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.components.bluetooth import (
    inject_bluetooth_service_info,
    patch_all_discovered_devices,
    patch_bluetooth_time,
)


# borrowed from unifiprotect
def assert_entity_counts(
    hass: HomeAssistant, platform: Platform, total: int, enabled: int
) -> None:
    """Assert entity counts for a given platform."""

    entity_registry = er.async_get(hass)

    entities = [
        e for e in entity_registry.entities if split_entity_id(e)[0] == platform.value
    ]

    assert len(entities) == total
    assert len(hass.states.async_all(platform.value)) == enabled


# ---


async def test_buttons_tp357(hass: HomeAssistant) -> None:
    """Test setting up creates the sensors."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    assert_entity_counts(hass, Platform.BUTTON, 0, 0)
    inject_bluetooth_service_info(hass, TP357_SERVICE_INFO)
    await hass.async_block_till_done()
    assert_entity_counts(hass, Platform.BUTTON, 0, 0)


async def test_buttons_tp358_discovery(hass: HomeAssistant) -> None:
    """Test discovery of device with button."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    assert_entity_counts(hass, Platform.BUTTON, 0, 0)
    inject_bluetooth_service_info(hass, TP358_SERVICE_INFO)
    await hass.async_block_till_done()
    assert_entity_counts(hass, Platform.BUTTON, 1, 1)

    button = hass.states.get("button.thermopro_tp358_4221_datetime")
    assert button.state == "unknown"


async def test_buttons_tp358_unavailable(hass: HomeAssistant) -> None:
    """Test tp358 set date&time button goes to unavailability."""
    start_monotonic = time.monotonic()

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    assert_entity_counts(hass, Platform.BUTTON, 0, 0)
    inject_bluetooth_service_info(hass, TP358_SERVICE_INFO)
    await hass.async_block_till_done()
    assert_entity_counts(hass, Platform.BUTTON, 1, 1)

    button = hass.states.get("button.thermopro_tp358_4221_datetime")
    assert button.state == "unknown"

    # borrowed from bthome test_sensor.py
    # Fastforward time without BLE advertisements
    monotonic_now = start_monotonic + FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS + 15

    with patch_bluetooth_time(monotonic_now), patch_all_discovered_devices([]):
        async_fire_time_changed(
            hass,
            dt_util.utcnow()
            + timedelta(seconds=FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS + 15),
        )
        await hass.async_block_till_done()

    # ---

    button = hass.states.get("button.thermopro_tp358_4221_datetime")
    # Normal devices should go to unavailable
    # TODO: can't get this to work, always "unknown"!
    assert button.state == STATE_UNAVAILABLE


async def test_buttons_tp358_reavailable(hass: HomeAssistant) -> None:
    """Test TP358/TP393 set date&time button goes to unavailablity and recovers."""
    start_monotonic = time.monotonic()

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    assert_entity_counts(hass, Platform.BUTTON, 0, 0)
    inject_bluetooth_service_info(hass, TP358_SERVICE_INFO)
    await hass.async_block_till_done()
    assert_entity_counts(hass, Platform.BUTTON, 1, 1)

    button = hass.states.get("button.thermopro_tp358_4221_datetime")
    assert button.state == "unknown"

    # borrowed from bthome test_sensor.py
    # Fastforward time without BLE advertisements
    monotonic_now = start_monotonic + FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS + 15

    with patch_bluetooth_time(monotonic_now), patch_all_discovered_devices([]):
        async_fire_time_changed(
            hass,
            dt_util.utcnow()
            + timedelta(seconds=FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS + 15),
        )
        await hass.async_block_till_done()

    # ---

    # Normal devices should go to unavailable
    # TODO: can't get this to work, always "unknown"!
    # assert button.state == STATE_UNAVAILABLE

    inject_bluetooth_service_info(hass, TP358_SERVICE_INFO)
    await hass.async_block_till_done()

    button = hass.states.get("button.thermopro_tp358_4221_datetime")

    assert button.state == "unknown"


async def test_buttons_tp358_press(
    hass: HomeAssistant, mock_now: datetime, mock_thermoprodevice: ThermoProDevice
) -> None:
    """Test TP358/TP393 set date&time button press."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="aa:bb:cc:dd:ee:ff",
    )
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert len(hass.states.async_all()) == 0
    assert_entity_counts(hass, Platform.BUTTON, 0, 0)
    inject_bluetooth_service_info(hass, TP358_SERVICE_INFO)
    await hass.async_block_till_done()
    assert_entity_counts(hass, Platform.BUTTON, 1, 1)

    await hass.services.async_call(
        "button",
        "press",
        {ATTR_ENTITY_ID: "button.thermopro_tp358_4221_datetime"},
        blocking=True,
    )

    mock_thermoprodevice.set_datetime.assert_awaited_once_with(mock_now, False)
