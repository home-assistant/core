"""Tests for the Bluetooth integration advertisement tracking."""

from datetime import timedelta
import time

# pylint: disable-next=no-name-in-module
from habluetooth.advertisement_tracker import ADVERTISING_TIMES_NEEDED
import pytest

from homeassistant.components.bluetooth import (
    async_get_learned_advertising_interval,
    async_register_scanner,
    async_track_unavailable,
)
from homeassistant.components.bluetooth.const import (
    FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS,
    SOURCE_LOCAL,
    UNAVAILABLE_TRACK_SECONDS,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.util import dt as dt_util

from . import (
    FakeScanner,
    generate_advertisement_data,
    generate_ble_device,
    inject_advertisement_with_time_and_source,
    inject_advertisement_with_time_and_source_connectable,
    patch_bluetooth_time,
)

from tests.common import async_fire_time_changed

ONE_HOUR_SECONDS = 3600


@pytest.mark.usefixtures("enable_bluetooth", "macos_adapter")
async def test_advertisment_interval_shorter_than_adapter_stack_timeout(
    hass: HomeAssistant,
) -> None:
    """Test we can determine the advertisement interval."""
    start_monotonic_time = time.monotonic()
    switchbot_device = generate_ble_device("44:44:33:11:23:12", "wohand")
    switchbot_adv = generate_advertisement_data(
        local_name="wohand", service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"]
    )
    switchbot_device_went_unavailable = False

    @callback
    def _switchbot_device_unavailable_callback(_address: str) -> None:
        """Switchbot device unavailable callback."""
        nonlocal switchbot_device_went_unavailable
        switchbot_device_went_unavailable = True

    for i in range(ADVERTISING_TIMES_NEEDED):
        inject_advertisement_with_time_and_source(
            hass,
            switchbot_device,
            switchbot_adv,
            start_monotonic_time + (i * 2),
            SOURCE_LOCAL,
        )

    assert async_get_learned_advertising_interval(
        hass, "44:44:33:11:23:12"
    ) == pytest.approx(2.0)

    switchbot_device_unavailable_cancel = async_track_unavailable(
        hass, _switchbot_device_unavailable_callback, switchbot_device.address
    )

    monotonic_now = start_monotonic_time + ((ADVERTISING_TIMES_NEEDED - 1) * 2)
    with patch_bluetooth_time(
        monotonic_now + UNAVAILABLE_TRACK_SECONDS,
    ):
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=UNAVAILABLE_TRACK_SECONDS)
        )
        await hass.async_block_till_done()

    assert switchbot_device_went_unavailable is True
    switchbot_device_unavailable_cancel()


@pytest.mark.usefixtures("enable_bluetooth", "macos_adapter")
async def test_advertisment_interval_longer_than_adapter_stack_timeout_connectable(
    hass: HomeAssistant,
) -> None:
    """Test device with a long advertisement interval."""
    start_monotonic_time = time.monotonic()
    switchbot_device = generate_ble_device("44:44:33:11:23:18", "wohand")
    switchbot_adv = generate_advertisement_data(
        local_name="wohand", service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"]
    )
    switchbot_device_went_unavailable = False

    @callback
    def _switchbot_device_unavailable_callback(_address: str) -> None:
        """Switchbot device unavailable callback."""
        nonlocal switchbot_device_went_unavailable
        switchbot_device_went_unavailable = True

    for i in range(ADVERTISING_TIMES_NEEDED):
        inject_advertisement_with_time_and_source(
            hass,
            switchbot_device,
            switchbot_adv,
            start_monotonic_time + (i * ONE_HOUR_SECONDS),
            SOURCE_LOCAL,
        )

    assert async_get_learned_advertising_interval(
        hass, "44:44:33:11:23:18"
    ) == pytest.approx(ONE_HOUR_SECONDS)

    switchbot_device_unavailable_cancel = async_track_unavailable(
        hass, _switchbot_device_unavailable_callback, switchbot_device.address
    )

    monotonic_now = start_monotonic_time + (
        (ADVERTISING_TIMES_NEEDED - 1) * ONE_HOUR_SECONDS
    )
    with patch_bluetooth_time(
        monotonic_now + UNAVAILABLE_TRACK_SECONDS,
    ):
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=UNAVAILABLE_TRACK_SECONDS)
        )
        await hass.async_block_till_done()

    assert switchbot_device_went_unavailable is True
    switchbot_device_unavailable_cancel()


@pytest.mark.usefixtures("enable_bluetooth", "macos_adapter")
async def test_advertisment_interval_longer_than_adapter_stack_timeout_adapter_change_connectable(
    hass: HomeAssistant,
) -> None:
    """Test device with a long advertisement interval with an adapter change."""
    start_monotonic_time = time.monotonic()
    switchbot_device = generate_ble_device("44:44:33:11:23:45", "wohand")
    switchbot_adv = generate_advertisement_data(
        local_name="wohand", service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"]
    )
    switchbot_device_went_unavailable = False

    @callback
    def _switchbot_device_unavailable_callback(_address: str) -> None:
        """Switchbot device unavailable callback."""
        nonlocal switchbot_device_went_unavailable
        switchbot_device_went_unavailable = True

    for i in range(ADVERTISING_TIMES_NEEDED):
        inject_advertisement_with_time_and_source(
            hass,
            switchbot_device,
            switchbot_adv,
            start_monotonic_time + (i * 2),
            "original",
        )

    assert async_get_learned_advertising_interval(
        hass, "44:44:33:11:23:45"
    ) == pytest.approx(2.0)

    for i in range(ADVERTISING_TIMES_NEEDED):
        inject_advertisement_with_time_and_source(
            hass,
            switchbot_device,
            switchbot_adv,
            start_monotonic_time + (i * ONE_HOUR_SECONDS),
            "new",
        )

    assert async_get_learned_advertising_interval(
        hass, "44:44:33:11:23:45"
    ) == pytest.approx(ONE_HOUR_SECONDS)

    switchbot_device_unavailable_cancel = async_track_unavailable(
        hass, _switchbot_device_unavailable_callback, switchbot_device.address
    )

    monotonic_now = start_monotonic_time + (
        (ADVERTISING_TIMES_NEEDED - 1) * ONE_HOUR_SECONDS
    )
    with patch_bluetooth_time(
        monotonic_now + UNAVAILABLE_TRACK_SECONDS,
    ):
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=UNAVAILABLE_TRACK_SECONDS)
        )
        await hass.async_block_till_done()

    assert switchbot_device_went_unavailable is True
    switchbot_device_unavailable_cancel()


@pytest.mark.usefixtures("enable_bluetooth", "macos_adapter")
async def test_advertisment_interval_longer_than_adapter_stack_timeout_not_connectable(
    hass: HomeAssistant,
) -> None:
    """Test device with a long advertisement interval that is not connectable not reaching the advertising interval."""
    start_monotonic_time = time.monotonic()
    switchbot_device = generate_ble_device("44:44:33:11:23:45", "wohand")
    switchbot_adv = generate_advertisement_data(
        local_name="wohand", service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"]
    )
    switchbot_device_went_unavailable = False

    @callback
    def _switchbot_device_unavailable_callback(_address: str) -> None:
        """Switchbot device unavailable callback."""
        nonlocal switchbot_device_went_unavailable
        switchbot_device_went_unavailable = True

    for i in range(ADVERTISING_TIMES_NEEDED):
        inject_advertisement_with_time_and_source(
            hass,
            switchbot_device,
            switchbot_adv,
            start_monotonic_time + (i * ONE_HOUR_SECONDS),
            SOURCE_LOCAL,
        )

    assert async_get_learned_advertising_interval(
        hass, "44:44:33:11:23:45"
    ) == pytest.approx(ONE_HOUR_SECONDS)

    switchbot_device_unavailable_cancel = async_track_unavailable(
        hass,
        _switchbot_device_unavailable_callback,
        switchbot_device.address,
        connectable=False,
    )

    monotonic_now = start_monotonic_time + (
        (ADVERTISING_TIMES_NEEDED - 1) * ONE_HOUR_SECONDS
    )
    with patch_bluetooth_time(
        monotonic_now + UNAVAILABLE_TRACK_SECONDS,
    ):
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=UNAVAILABLE_TRACK_SECONDS)
        )
        await hass.async_block_till_done()

    assert switchbot_device_went_unavailable is False
    switchbot_device_unavailable_cancel()


@pytest.mark.usefixtures("enable_bluetooth", "macos_adapter")
async def test_advertisment_interval_shorter_than_adapter_stack_timeout_adapter_change_not_connectable(
    hass: HomeAssistant,
) -> None:
    """Test device with a short advertisement interval with an adapter change that is not connectable."""
    start_monotonic_time = time.monotonic()
    switchbot_device = generate_ble_device("44:44:33:11:23:5C", "wohand")
    switchbot_adv = generate_advertisement_data(
        local_name="wohand",
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
        rssi=-100,
    )
    switchbot_device_went_unavailable = False

    @callback
    def _switchbot_device_unavailable_callback(_address: str) -> None:
        """Switchbot device unavailable callback."""
        nonlocal switchbot_device_went_unavailable
        switchbot_device_went_unavailable = True

    for i in range(ADVERTISING_TIMES_NEEDED):
        inject_advertisement_with_time_and_source(
            hass,
            switchbot_device,
            switchbot_adv,
            start_monotonic_time + (i * ONE_HOUR_SECONDS),
            "original",
        )

    assert async_get_learned_advertising_interval(
        hass, "44:44:33:11:23:5C"
    ) == pytest.approx(ONE_HOUR_SECONDS)

    switchbot_adv_better_rssi = generate_advertisement_data(
        local_name="wohand",
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
        rssi=-30,
    )
    for i in range(ADVERTISING_TIMES_NEEDED):
        inject_advertisement_with_time_and_source(
            hass,
            switchbot_device,
            switchbot_adv_better_rssi,
            start_monotonic_time + (i * 2),
            "new",
        )

    assert async_get_learned_advertising_interval(
        hass, "44:44:33:11:23:5C"
    ) == pytest.approx(2.0)

    switchbot_device_unavailable_cancel = async_track_unavailable(
        hass,
        _switchbot_device_unavailable_callback,
        switchbot_device.address,
        connectable=False,
    )

    monotonic_now = start_monotonic_time + (
        (ADVERTISING_TIMES_NEEDED - 1) * ONE_HOUR_SECONDS
    )
    with patch_bluetooth_time(
        monotonic_now + UNAVAILABLE_TRACK_SECONDS,
    ):
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=UNAVAILABLE_TRACK_SECONDS)
        )
        await hass.async_block_till_done()

    assert switchbot_device_went_unavailable is True
    switchbot_device_unavailable_cancel()


@pytest.mark.usefixtures("enable_bluetooth", "macos_adapter")
async def test_advertisment_interval_longer_than_adapter_stack_timeout_adapter_change_not_connectable(
    hass: HomeAssistant,
) -> None:
    """Test device with a long advertisement interval with an adapter change that is not connectable."""
    start_monotonic_time = time.monotonic()
    switchbot_device = generate_ble_device("44:44:33:11:23:45", "wohand")
    switchbot_adv = generate_advertisement_data(
        local_name="wohand",
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
        rssi=-100,
    )
    switchbot_device_went_unavailable = False

    scanner = FakeScanner("new", "fake_adapter")
    cancel_scanner = async_register_scanner(hass, scanner)

    @callback
    def _switchbot_device_unavailable_callback(_address: str) -> None:
        """Switchbot device unavailable callback."""
        nonlocal switchbot_device_went_unavailable
        switchbot_device_went_unavailable = True

    for i in range(ADVERTISING_TIMES_NEEDED):
        inject_advertisement_with_time_and_source_connectable(
            hass,
            switchbot_device,
            switchbot_adv,
            start_monotonic_time + (i * 2),
            "original",
            connectable=False,
        )

    assert async_get_learned_advertising_interval(
        hass, "44:44:33:11:23:45"
    ) == pytest.approx(2.0)

    switchbot_better_rssi_adv = generate_advertisement_data(
        local_name="wohand",
        service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"],
        rssi=-30,
    )
    for i in range(ADVERTISING_TIMES_NEEDED):
        inject_advertisement_with_time_and_source_connectable(
            hass,
            switchbot_device,
            switchbot_better_rssi_adv,
            start_monotonic_time + (i * ONE_HOUR_SECONDS),
            "new",
            connectable=False,
        )

    assert async_get_learned_advertising_interval(
        hass, "44:44:33:11:23:45"
    ) == pytest.approx(ONE_HOUR_SECONDS)

    switchbot_device_unavailable_cancel = async_track_unavailable(
        hass,
        _switchbot_device_unavailable_callback,
        switchbot_device.address,
        connectable=False,
    )

    monotonic_now = start_monotonic_time + (
        (ADVERTISING_TIMES_NEEDED - 1) * ONE_HOUR_SECONDS
    )
    with patch_bluetooth_time(
        monotonic_now + UNAVAILABLE_TRACK_SECONDS,
    ):
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=UNAVAILABLE_TRACK_SECONDS)
        )
        await hass.async_block_till_done()

    assert switchbot_device_went_unavailable is False
    cancel_scanner()

    # Now that the scanner is gone we should go back to the stack default timeout
    with patch_bluetooth_time(
        monotonic_now + UNAVAILABLE_TRACK_SECONDS,
    ):
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=UNAVAILABLE_TRACK_SECONDS)
        )
        await hass.async_block_till_done()

    assert switchbot_device_went_unavailable is False

    # Now that the scanner is gone we should go back to the stack default timeout
    with patch_bluetooth_time(
        monotonic_now + UNAVAILABLE_TRACK_SECONDS,
    ):
        async_fire_time_changed(
            hass,
            dt_util.utcnow()
            + timedelta(seconds=FALLBACK_MAXIMUM_STALE_ADVERTISEMENT_SECONDS),
        )
        await hass.async_block_till_done()

    assert switchbot_device_went_unavailable is False

    switchbot_device_unavailable_cancel()


@pytest.mark.usefixtures("enable_bluetooth", "macos_adapter")
async def test_advertisment_interval_longer_increasing_than_adapter_stack_timeout_adapter_change_not_connectable(
    hass: HomeAssistant,
) -> None:
    """Test device with a increasing advertisement interval with an adapter change that is not connectable."""
    start_monotonic_time = time.monotonic()
    switchbot_device = generate_ble_device("44:44:33:11:23:45", "wohand")
    switchbot_adv = generate_advertisement_data(
        local_name="wohand", service_uuids=["cba20d00-224d-11e6-9fb8-0002a5d5c51b"]
    )
    switchbot_device_went_unavailable = False

    @callback
    def _switchbot_device_unavailable_callback(_address: str) -> None:
        """Switchbot device unavailable callback."""
        nonlocal switchbot_device_went_unavailable
        switchbot_device_went_unavailable = True

    for i in range(ADVERTISING_TIMES_NEEDED, 2 * ADVERTISING_TIMES_NEEDED):
        inject_advertisement_with_time_and_source(
            hass,
            switchbot_device,
            switchbot_adv,
            start_monotonic_time + (i**2),
            "new",
        )

    assert async_get_learned_advertising_interval(
        hass, "44:44:33:11:23:45"
    ) == pytest.approx(61.0)

    switchbot_device_unavailable_cancel = async_track_unavailable(
        hass,
        _switchbot_device_unavailable_callback,
        switchbot_device.address,
        connectable=False,
    )

    monotonic_now = start_monotonic_time + UNAVAILABLE_TRACK_SECONDS + 1
    with patch_bluetooth_time(
        monotonic_now + UNAVAILABLE_TRACK_SECONDS,
    ):
        async_fire_time_changed(
            hass, dt_util.utcnow() + timedelta(seconds=UNAVAILABLE_TRACK_SECONDS)
        )
        await hass.async_block_till_done()

    assert switchbot_device_went_unavailable is False
    switchbot_device_unavailable_cancel()
