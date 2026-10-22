"""Test the Tridonic DALI coordinator."""

from types import GeneratorType, SimpleNamespace
from unittest.mock import patch

from dali.exceptions import TransmissionError
from dali.gear.general import QueryControlGearPresent, QueryMaxLevel, QueryMinLevel
from dali.gear.led import QueryDimmingCurve
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.dali.const import DOMAIN
from homeassistant.components.dali.coordinator import (
    DaliCoordinator,
    DaliGearData,
    _brightness_to_dali_level,
    _dali_level_to_brightness,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from .conftest import FakeDaliDriver


@pytest.fixture
def coordinator(
    hass: HomeAssistant, fake_dali_driver: FakeDaliDriver
) -> DaliCoordinator:
    """Return a DALI coordinator with a fake driver."""
    entry = MockConfigEntry(domain=DOMAIN)
    return DaliCoordinator(hass, fake_dali_driver, entry)


@pytest.mark.parametrize(
    ("level", "linear", "expected"),
    [
        (255, False, None),
        (0, False, 0),
        (86, False, 3),
        (170, True, 171),
        (200, False, 58),
        (200, True, 201),
        (254, False, 255),
        (254, True, 255),
    ],
)
def test_dali_level_to_brightness(
    level: object, linear: bool, expected: int | None
) -> None:
    """Test DALI readback conversion branches."""
    assert _dali_level_to_brightness(level, linear) == expected


def test_linear_readback_is_independent_of_minimum() -> None:
    """Test the linear readback is a fixed curve; the minimum only clamps commands.

    Level 200 reads back the same brightness whatever the configured minimum,
    and a request below the minimum is clamped to it rather than rescaled.
    """
    assert _dali_level_to_brightness(200, True) == 201
    # Mid brightness maps near mid level, far below a raised minimum.
    assert _brightness_to_dali_level(128, True, 1) < 200
    # With a raised minimum the command clamps to it instead of driving higher.
    assert _brightness_to_dali_level(128, True, 200) == 200


async def test_invalid_min_level_uses_default(
    coordinator: DaliCoordinator, fake_dali_driver: FakeDaliDriver
) -> None:
    """Test invalid physical minimum levels fall back to one."""
    fake_dali_driver.min_levels[0] = 255

    gear = await coordinator._query_gear(0)

    assert gear is not None
    assert gear.min_level == 1


async def test_gear_config_min_max_is_decoded(
    coordinator: DaliCoordinator, fake_dali_driver: FakeDaliDriver
) -> None:
    """Test the min/max dimming levels are read for a gear."""
    gear = await coordinator._query_gear(0)

    assert gear is not None
    assert gear.min_level == 86
    assert gear.max_level == 254


async def test_invalid_max_level_is_discarded(
    coordinator: DaliCoordinator, fake_dali_driver: FakeDaliDriver
) -> None:
    """Test an out-of-range maximum level is reported as no value."""
    fake_dali_driver.max_levels[0] = 255

    gear = await coordinator._query_gear(0)

    assert gear is not None
    assert gear.max_level is None


async def test_linear_dimming_curve_is_read(
    coordinator: DaliCoordinator, fake_dali_driver: FakeDaliDriver
) -> None:
    """Test the DT6 dimming curve selects the linear mapping."""
    gear = await coordinator._query_gear(0)

    assert gear is not None
    assert gear.linear_dimming is True


async def test_missing_dimming_curve_is_retried(
    coordinator: DaliCoordinator, fake_dali_driver: FakeDaliDriver
) -> None:
    """Test a dropped dimming-curve reply re-reads instead of flipping the curve."""
    # Seed the linear gear 0 as known so a miss triggers the retry.
    coordinator.data = {0: await coordinator._query_gear_once(0)}

    curve_reads = 0
    original_send = fake_dali_driver.send

    async def send(command: object) -> object:
        nonlocal curve_reads
        if isinstance(command, QueryDimmingCurve):
            curve_reads += 1
            if curve_reads == 1:
                return SimpleNamespace(raw_value=None)
        return await original_send(command)

    with patch.object(fake_dali_driver, "send", side_effect=send):
        gear = await coordinator._query_gear(0)

    assert curve_reads == 2
    assert gear is not None
    assert gear.linear_dimming is True


async def test_framing_error_dimming_curve_is_rejected(
    coordinator: DaliCoordinator, fake_dali_driver: FakeDaliDriver
) -> None:
    """Test a framing-error dimming-curve reply is treated as a miss."""
    original_send = fake_dali_driver.send

    async def send(command: object) -> object:
        if isinstance(command, QueryDimmingCurve):
            return SimpleNamespace(raw_value=SimpleNamespace(error=True, as_integer=1))
        return await original_send(command)

    with patch.object(fake_dali_driver, "send", side_effect=send):
        assert await coordinator._query_gear_once(0) is None


async def test_missing_min_level_keeps_cached_value(
    coordinator: DaliCoordinator, fake_dali_driver: FakeDaliDriver
) -> None:
    """Test a dropped minimum-level reply keeps the known minimum."""
    gear = await coordinator._query_gear_once(0)
    assert gear is not None
    assert gear.min_level == 86
    coordinator.data = {0: gear}

    original_send = fake_dali_driver.send

    async def send(command: object) -> object:
        if isinstance(command, QueryMinLevel):
            return SimpleNamespace(value=None)
        return await original_send(command)

    with patch.object(fake_dali_driver, "send", side_effect=send):
        refreshed = await coordinator._query_gear_once(0)

    assert refreshed is not None
    assert refreshed.min_level == 86


async def test_missing_max_level_keeps_cached_value(
    coordinator: DaliCoordinator, fake_dali_driver: FakeDaliDriver
) -> None:
    """Test a dropped maximum-level reply keeps the known maximum.

    Clearing a known maximum would lift the command clamp and let a full-power
    request drive above the gear's rated ceiling.
    """
    fake_dali_driver.max_levels[0] = 200
    gear = await coordinator._query_gear_once(0)
    assert gear is not None
    assert gear.max_level == 200
    coordinator.data = {0: gear}

    original_send = fake_dali_driver.send

    async def send(command: object) -> object:
        if isinstance(command, QueryMaxLevel):
            return SimpleNamespace(value=None)
        return await original_send(command)

    with patch.object(fake_dali_driver, "send", side_effect=send):
        refreshed = await coordinator._query_gear_once(0)

    assert refreshed is not None
    assert refreshed.max_level == 200


async def test_communication_failure_raises_update_failed(
    coordinator: DaliCoordinator, fake_dali_driver: FakeDaliDriver
) -> None:
    """Test communication failures become coordinator update failures."""
    with (
        patch.object(fake_dali_driver, "send", side_effect=OSError("offline")),
        pytest.raises(UpdateFailed),
    ):
        await coordinator._query_gear(0)


async def test_scan_isolates_single_gear_transmission_error(
    coordinator: DaliCoordinator, fake_dali_driver: FakeDaliDriver
) -> None:
    """Test one gear rejecting a frame does not abort discovery of the rest.

    A transmission error on the lowest address must not stop the scan before it
    reaches the higher-addressed gear, so the bus is not left with only the
    first gear discovered.
    """
    original_send = fake_dali_driver.send

    async def send(msg: object, **kwargs: object) -> object:
        if isinstance(msg, QueryControlGearPresent) and msg.destination.address == 0:
            raise TransmissionError(1)
        return await original_send(msg, **kwargs)

    with patch.object(fake_dali_driver, "send", side_effect=send):
        data = await coordinator._async_update_data()

    assert 0 not in data
    assert 2 in data


async def test_scan_bus_wide_transmission_error_yields_no_gear(
    coordinator: DaliCoordinator, fake_dali_driver: FakeDaliDriver
) -> None:
    """Test a bus-wide transmission error takes every gear unavailable, not fatal.

    When every frame is rejected the scan completes with no gear rather than
    raising, so the lights go unavailable and recover on the next good scan.
    """
    with patch.object(fake_dali_driver, "send", side_effect=TransmissionError(1)):
        data = await coordinator._async_update_data()

    assert data == {}


async def test_async_update_gear_touches_single_entry(
    coordinator: DaliCoordinator, fake_dali_driver: FakeDaliDriver
) -> None:
    """Test a targeted update refreshes one gear without a full bus scan."""
    coordinator.data = {5: SimpleNamespace()}

    await coordinator.async_update_gear(0)

    assert 0 in coordinator.data
    assert not any(
        isinstance(command, QueryControlGearPresent)
        and command.destination.address != 0
        for command in fake_dali_driver.sent
    )


async def test_async_update_gear_optimistic_level_overrides_readback(
    coordinator: DaliCoordinator, fake_dali_driver: FakeDaliDriver
) -> None:
    """Test a just-sent level is shown at once, then reconciled by a later scan.

    A gear fades to a commanded level, so an immediate read returns a mid-fade
    value. ``optimistic_level`` publishes the target straight away; a later plain
    refresh publishes the device's actual readback.
    """
    # The fake gear reports actual level 128; the override wins over that read.
    await coordinator.async_update_gear(0, optimistic_level=50)
    assert coordinator.data[0].level == 50

    # A refresh without an override reconciles to the device readback (raw level
    # 128 on the linear curve reads back as brightness 129).
    await coordinator.async_update_gear(0)
    assert coordinator.data[0].level == 129


async def test_async_update_gear_drops_absent_gear(
    coordinator: DaliCoordinator,
) -> None:
    """Test a targeted update removes a gear that stopped responding."""
    coordinator.data = {5: SimpleNamespace()}

    await coordinator.async_update_gear(5)

    assert 5 not in coordinator.data


async def test_known_gear_survives_transient_presence_miss(
    coordinator: DaliCoordinator, fake_dali_driver: FakeDaliDriver
) -> None:
    """Test a known gear is re-queried after a dropped presence response."""
    coordinator.data = {0: DaliGearData(device_types=(6,))}
    original_send = fake_dali_driver.send
    attempts = 0

    async def send(command: object) -> object:
        nonlocal attempts
        if (
            isinstance(command, QueryControlGearPresent)
            and command.destination.address == 0
        ):
            attempts += 1
            if attempts == 1:
                return SimpleNamespace(value=False)
        return await original_send(command)

    with patch.object(fake_dali_driver, "send", side_effect=send):
        gear = await coordinator._query_gear(0)

    assert attempts == 2
    assert gear is not None


async def test_known_gear_reuses_cached_device_types(
    coordinator: DaliCoordinator, fake_dali_driver: FakeDaliDriver
) -> None:
    """Test a known gear's refresh does not re-query its static device types."""
    coordinator.data = {0: DaliGearData(device_types=(6,))}
    original_send = fake_dali_driver.send
    sequence_sends = 0

    async def send(command: object, **kwargs: object) -> object:
        nonlocal sequence_sends
        if isinstance(command, GeneratorType):
            sequence_sends += 1
        return await original_send(command, **kwargs)

    with patch.object(fake_dali_driver, "send", side_effect=send):
        gear = await coordinator._query_gear(0)

    assert sequence_sends == 0
    assert gear is not None
    assert gear.device_types == (6,)


async def test_absent_address_is_not_retried(
    coordinator: DaliCoordinator, fake_dali_driver: FakeDaliDriver
) -> None:
    """Test an unknown address is not re-queried, avoiding extra bus traffic."""
    attempts = 0
    original_send = fake_dali_driver.send

    async def send(command: object) -> object:
        nonlocal attempts
        if (
            isinstance(command, QueryControlGearPresent)
            and command.destination.address == 5
        ):
            attempts += 1
        return await original_send(command)

    with patch.object(fake_dali_driver, "send", side_effect=send):
        gear = await coordinator._query_gear(5)

    assert attempts == 1
    assert gear is None


async def test_device_info_for_unknown_address(
    coordinator: DaliCoordinator,
) -> None:
    """Test device info falls back to defaults for an unknown gear."""
    coordinator.data = {}

    device_info = coordinator.device_info("entry", "USB-DALI2", 5)

    assert device_info["name"] == "USB-DALI2/5 (gear)"
    assert device_info["model"] == "DALI control gear (address 5)"
    assert device_info["serial_number"] is None


async def test_device_info_uses_gtin_as_model_id(
    coordinator: DaliCoordinator,
) -> None:
    """Test the GTIN populates model_id only, so it is not shown twice."""
    coordinator.data = {5: DaliGearData(gtin=1234567654321)}

    device_info = coordinator.device_info("entry", "USB-DALI2", 5)

    assert device_info["model"] == "DALI control gear (address 5)"
    assert device_info["model_id"] == "1234567654321"


async def test_device_info_reports_the_serial_number(
    coordinator: DaliCoordinator,
) -> None:
    """Test the gear's serial number reaches the registry device."""
    coordinator.data = {5: DaliGearData(serial_no="080706")}

    device_info = coordinator.device_info("entry", "USB-DALI2", 5)

    assert device_info["serial_number"] == "080706"


async def test_device_info_model_exposes_gear_device_type(
    coordinator: DaliCoordinator,
) -> None:
    """Test a gear's model names its device type and IEC 62386 part."""
    coordinator.data = {5: DaliGearData(device_types=(6,))}

    device_info = coordinator.device_info("entry", "USB-DALI2", 5)

    assert device_info["model"] == (
        "DALI control gear – LED module (DT6, IEC 62386-207) (address 5)"
    )


async def test_device_info_uses_short_usb_label(
    hass: HomeAssistant, fake_dali_driver: FakeDaliDriver
) -> None:
    """Test the device name is derived from the USB unique ID, not the title."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="17B5:0201_000000024994_Lunatone_DALI-2 USB PS",
        title="DALI-2 USB PS - /dev/serial/by-id/usb-Lunatone_DALI-2_USB_PS - Lunatone",
    )
    coordinator = DaliCoordinator(hass, fake_dali_driver, entry)
    coordinator.data = {}

    device_info = coordinator.device_info(entry.entry_id, entry.title, 0)

    assert device_info["name"] == "DALI-2_USB_PS_000000024994/0 (gear)"
