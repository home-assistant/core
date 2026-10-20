"""Test the Tridonic DALI integration setup."""

from types import GeneratorType, SimpleNamespace
from unittest.mock import AsyncMock, patch

from dali.exceptions import DALISequenceError
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.dali import async_remove_config_entry_device
from homeassistant.components.dali.const import DOMAIN
from homeassistant.components.dali.coordinator import SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant

from .conftest import FakeDaliDriver


async def test_setup_and_unload_entry(
    hass: HomeAssistant, fake_dali_driver: FakeDaliDriver
) -> None:
    """Test setup scans and retains the supported DT6 control gear."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: "/dev/ttyACM0"},
        title="USB-DALI2",
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.dali.DriverLubaRs232",
            return_value=fake_dali_driver,
        ),
        patch.object(
            hass.config_entries, "async_forward_entry_setups", new_callable=AsyncMock
        ) as forward_setups,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)

    assert entry.runtime_data.data.keys() == {0, 2}
    assert entry.runtime_data.data[0].min_level == 86
    assert forward_setups.await_count == 1

    assert await hass.config_entries.async_unload(entry.entry_id)

    assert fake_dali_driver.closed


async def test_setup_entry_with_no_supported_gear(
    hass: HomeAssistant, fake_dali_driver: FakeDaliDriver
) -> None:
    """Test setup succeeds when the DALI bus has no DT6 gear."""
    fake_dali_driver.gears = {}
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_DEVICE: "/dev/ttyACM0"},
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.dali.DriverLubaRs232",
            return_value=fake_dali_driver,
        ),
        patch.object(
            hass.config_entries, "async_forward_entry_setups", new_callable=AsyncMock
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)

    assert entry.runtime_data.data == {}
    entry.runtime_data.close()


async def test_setup_entry_connection_failure(
    hass: HomeAssistant, fake_dali_driver: FakeDaliDriver
) -> None:
    """Test setup closes the driver when connection fails."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_DEVICE: "/dev/ttyACM0"})
    entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.dali.DriverLubaRs232",
            return_value=fake_dali_driver,
        ),
        patch.object(fake_dali_driver, "connect", side_effect=OSError("offline")),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)

    assert fake_dali_driver.closed


async def test_setup_entry_refresh_failure(
    hass: HomeAssistant, fake_dali_driver: FakeDaliDriver
) -> None:
    """Test setup closes the driver when the first refresh fails."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_DEVICE: "/dev/ttyACM0"})
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.dali.DriverLubaRs232",
            return_value=fake_dali_driver,
        ),
        patch.object(fake_dali_driver, "send", side_effect=OSError("offline")),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)

    assert fake_dali_driver.closed


async def test_lost_interface_is_reconnected(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_dali_driver: FakeDaliDriver,
) -> None:
    """Test a replugged interface is reconnected and the bus scanned again."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_DEVICE: "/dev/ttyACM0"}, title="USB-DALI2"
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.dali.DriverLubaRs232",
        return_value=fake_dali_driver,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        # The interface is unplugged, so its serial transport goes away.
        fake_dali_driver.connected = False
        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert fake_dali_driver.is_connected
    assert entry.runtime_data.data.keys() == {0, 2}


async def test_lost_interface_retries_while_it_stays_away(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_dali_driver: FakeDaliDriver,
) -> None:
    """Test the entry retries in the background while the interface is gone."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_DEVICE: "/dev/ttyACM0"}, title="USB-DALI2"
    )
    entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.dali.DriverLubaRs232",
        return_value=fake_dali_driver,
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

        fake_dali_driver.connected = False
        with patch.object(
            fake_dali_driver, "connect", side_effect=OSError("unplugged")
        ):
            freezer.tick(SCAN_INTERVAL)
            async_fire_time_changed(hass)
            await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_setup_entry_dali_sequence_failure(
    hass: HomeAssistant, fake_dali_driver: FakeDaliDriver
) -> None:
    """Test setup ignores a gear when its device-type query fails."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_DEVICE: "/dev/ttyACM0"})
    entry.add_to_hass(hass)
    original_send = fake_dali_driver.send

    async def send(
        msg: object, *, priority: int = 5, progress: object = None
    ) -> object:
        if isinstance(msg, GeneratorType) and msg.__name__ == "QueryDeviceTypes":
            msg.close()
            raise DALISequenceError
        return await original_send(msg, priority=priority, progress=progress)

    with (
        patch(
            "homeassistant.components.dali.DriverLubaRs232",
            return_value=fake_dali_driver,
        ),
        patch.object(fake_dali_driver, "send", side_effect=send),
        patch.object(
            hass.config_entries, "async_forward_entry_setups", new_callable=AsyncMock
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)

    assert entry.runtime_data.data == {}
    assert await hass.config_entries.async_unload(entry.entry_id)


@pytest.mark.parametrize(
    ("identifiers", "removable"),
    [
        pytest.param({(DOMAIN, "ENTRY_gear_0")}, False, id="active_gear"),
        pytest.param({(DOMAIN, "ENTRY_gear_5")}, True, id="stale_gear_address"),
        pytest.param({("other", "ENTRY_gear_0")}, True, id="foreign_identifier"),
    ],
)
async def test_remove_config_entry_device(
    hass: HomeAssistant,
    fake_dali_driver: FakeDaliDriver,
    identifiers: set[tuple[str, str]],
    removable: bool,
) -> None:
    """Test devices can only be removed once their address stops responding."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_DEVICE: "/dev/ttyACM0"}, entry_id="ENTRY"
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.dali.DriverLubaRs232",
            return_value=fake_dali_driver,
        ),
        patch.object(
            hass.config_entries, "async_forward_entry_setups", new_callable=AsyncMock
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)

    device_entry = SimpleNamespace(identifiers=identifiers)
    assert (
        await async_remove_config_entry_device(hass, entry, device_entry) is removable
    )

    entry.runtime_data.close()
