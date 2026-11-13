"""Test the Tridonic DALI integration setup."""

import asyncio
import logging
from types import GeneratorType, SimpleNamespace
from unittest.mock import AsyncMock, patch

from dali.exceptions import DALISequenceError
from freezegun.api import FrozenDateTimeFactory
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_fire_time_changed

from homeassistant.components.dali import async_remove_config_entry_device
from homeassistant.components.dali.const import DOMAIN
from homeassistant.components.dali.coordinator import FULL_SCAN_INTERVAL, SCAN_INTERVAL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_DEVICE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

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


async def test_setup_closes_transport_when_connect_is_cancelled(
    hass: HomeAssistant, fake_dali_driver: FakeDaliDriver
) -> None:
    """Test a cancelled connect still closes the serial transport."""
    entry = MockConfigEntry(domain=DOMAIN, data={CONF_DEVICE: "/dev/ttyACM0"})
    entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.dali.DriverLubaRs232",
            return_value=fake_dali_driver,
        ),
        patch.object(fake_dali_driver, "connect", side_effect=asyncio.CancelledError),
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


async def test_single_gear_update_keeps_the_scan_schedule(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_dali_driver: FakeDaliDriver,
) -> None:
    """Test frequent single-gear updates do not postpone the periodic scan.

    Publishing a command update must not reschedule the coordinator's refresh,
    or repeated commands to one light would indefinitely starve the discovery
    and refresh of the other gear.
    """
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
        coordinator = entry.runtime_data

        with patch.object(
            coordinator,
            "_async_update_data",
            wraps=coordinator._async_update_data,
        ) as scan:
            # A command two thirds into the interval must not push the next scan
            # out; it still fires at the original deadline.
            freezer.tick(SCAN_INTERVAL * 2 / 3)
            await coordinator.async_update_gear(0)
            assert scan.call_count == 0

            freezer.tick(SCAN_INTERVAL / 3)
            async_fire_time_changed(hass)
            await hass.async_block_till_done()
            assert scan.call_count == 1


async def test_logs_gear_unavailable_and_recovery_once(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_dali_driver: FakeDaliDriver,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Test a gear going unavailable and recovering is logged once each."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_DEVICE: "/dev/ttyACM0"}, title="USB-DALI2"
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.dali.DriverLubaRs232",
            return_value=fake_dali_driver,
        ),
        caplog.at_level(logging.INFO, "homeassistant.components.dali.coordinator"),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.runtime_data.data.keys() == {0, 2}
        # A first discovery is not a recovery.
        assert "responding again" not in caplog.text

        # A gear stops responding; the next scan reports it exactly once.
        fake_dali_driver.gears.pop(2)
        caplog.clear()
        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert entry.runtime_data.data.keys() == {0}
        assert caplog.text.count("DALI control gear 2 stopped responding") == 1

        # It comes back; the next full scan reports the recovery exactly once.
        fake_dali_driver.gears[2] = (6,)
        caplog.clear()
        freezer.tick(FULL_SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert entry.runtime_data.data.keys() == {0, 2}
        assert caplog.text.count("DALI control gear 2 is responding again") == 1


async def test_deleted_light_is_rediscovered(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    fake_dali_driver: FakeDaliDriver,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test a light deleted from the registry is recreated when the gear reappears."""
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

        unique_id = f"{entry.entry_id}_0"
        entity_id = entity_registry.async_get_entity_id("light", DOMAIN, unique_id)
        assert entity_id is not None

        # Deleting the device deletes its light; the address must stop being
        # tracked so the gear can be rediscovered.
        entity_registry.async_remove(entity_id)
        await hass.async_block_till_done()
        assert entity_registry.async_get_entity_id("light", DOMAIN, unique_id) is None

        freezer.tick(SCAN_INTERVAL)
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert (
            entity_registry.async_get_entity_id("light", DOMAIN, unique_id) is not None
        )

    entry.runtime_data.close()


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


async def test_remove_device_allowed_when_setup_failed(
    hass: HomeAssistant, fake_dali_driver: FakeDaliDriver
) -> None:
    """Test a stale device can be removed when setup left no runtime data."""
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_DEVICE: "/dev/ttyACM0"}, entry_id="ENTRY"
    )
    entry.add_to_hass(hass)
    with (
        patch(
            "homeassistant.components.dali.DriverLubaRs232",
            return_value=fake_dali_driver,
        ),
        patch.object(fake_dali_driver, "connect", side_effect=OSError("offline")),
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)

    assert not hasattr(entry, "runtime_data")
    device_entry = SimpleNamespace(identifiers={(DOMAIN, "ENTRY_gear_0")})
    assert await async_remove_config_entry_device(hass, entry, device_entry) is True
