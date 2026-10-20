"""Test the Tridonic DALI coordinator."""

from types import SimpleNamespace
from unittest.mock import patch

from dali.exceptions import TransmissionError
from dali.gear.general import QueryControlGearPresent, QueryMinLevel
from dali.gear.led import QueryDimmingCurve
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.dali.const import CONF_BUS_POWER, DOMAIN
from homeassistant.components.dali.coordinator import (
    DaliCoordinator,
    DaliGearData,
    _dali_level_to_brightness,
)
from homeassistant.const import CONF_DEVICE
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
        (86, False, 1),
        (170, True, 128),
        (254, False, 255),
        (254, True, 255),
    ],
)
def test_dali_level_to_brightness(
    level: object, linear: bool, expected: int | None
) -> None:
    """Test DALI readback conversion branches."""
    assert _dali_level_to_brightness(level, linear, 86) == expected


@pytest.mark.parametrize("linear", [False, True])
def test_dali_level_to_brightness_full_output_overrides_min_level(
    linear: bool,
) -> None:
    """Test full arc power reports full brightness even when min_level is 254."""
    assert _dali_level_to_brightness(254, linear, 254) == 255


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


async def test_communication_failure_raises_update_failed(
    coordinator: DaliCoordinator, fake_dali_driver: FakeDaliDriver
) -> None:
    """Test communication failures become coordinator update failures."""
    with (
        patch.object(fake_dali_driver, "send", side_effect=OSError("offline")),
        pytest.raises(UpdateFailed),
    ):
        await coordinator._query_gear(0)


async def test_update_transmission_error_fails_update(
    hass: HomeAssistant,
    fake_dali_driver: FakeDaliDriver,
) -> None:
    """Test an interface transmission error mid-scan fails the update."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_DEVICE: "/dev/ttyACM0", CONF_BUS_POWER: True}
    )
    entry.add_to_hass(hass)
    coordinator = DaliCoordinator(hass, fake_dali_driver, entry)

    with (
        patch.object(fake_dali_driver, "send", side_effect=TransmissionError(1)),
        pytest.raises(UpdateFailed),
    ):
        await coordinator._async_update_data()


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
    coordinator.data = {0: SimpleNamespace()}
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
