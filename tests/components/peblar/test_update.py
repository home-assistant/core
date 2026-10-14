"""Tests for the Peblar update platform."""

import asyncio
from datetime import timedelta
from unittest.mock import MagicMock

from freezegun.api import FrozenDateTimeFactory
from peblar import PackageType, PeblarConnectionError, PeblarVersions
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.peblar.const import DOMAIN
from homeassistant.components.update import (
    ATTR_IN_PROGRESS,
    DOMAIN as UPDATE_DOMAIN,
    SERVICE_INSTALL,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry, async_fire_time_changed, snapshot_platform


async def _async_offer_both_updates(
    hass: HomeAssistant, mock_peblar: MagicMock
) -> None:
    """Put the charger on older packages, so both updates are on offer."""
    mock_peblar.current_versions.return_value = PeblarVersions.from_dict(
        {"Customization": "Peblar-1.8", "Firmware": "1.6.1+1+WL-1"}
    )
    mock_peblar.available_versions.return_value = PeblarVersions.from_dict(
        {"Customization": "Peblar-1.9", "Firmware": "1.6.2+1+WL-1"}
    )
    await hass.config_entries.async_reload(
        hass.config_entries.async_entries(DOMAIN)[0].entry_id
    )
    await hass.async_block_till_done()


@pytest.mark.parametrize("init_integration", [Platform.UPDATE], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_entities(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
    entity_registry: er.EntityRegistry,
    device_registry: dr.DeviceRegistry,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test the update entities."""
    await snapshot_platform(hass, entity_registry, snapshot, mock_config_entry.entry_id)

    # Ensure all entities are correctly assigned to the Peblar EV charger
    device_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "23-45-A4O-MOF"), mock_config_entry.entry_id
    )
    assert device_entry
    entity_entries = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    for entity_entry in entity_entries:
        assert entity_entry.device_id == device_entry.id


@pytest.mark.parametrize("init_integration", [Platform.UPDATE], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_install_firmware(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
) -> None:
    """Test installing the firmware asks the charger for that package.

    Only the firmware is out of date in the fixtures, which is the case
    where installing it straight away is fine.
    """
    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: "update.peblar_ev_charger_firmware"},
        blocking=True,
    )

    mock_peblar.update.assert_called_once_with(package_type=PackageType.FIRMWARE)


@pytest.mark.parametrize("init_integration", [Platform.UPDATE], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_install_customization(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
) -> None:
    """Test installing the customization asks the charger for that package."""
    await _async_offer_both_updates(hass, mock_peblar)

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: "update.peblar_ev_charger_customization"},
        blocking=True,
    )

    mock_peblar.update.assert_called_once_with(package_type=PackageType.CUSTOMIZATION)


@pytest.mark.parametrize("init_integration", [Platform.UPDATE], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_install_firmware_refuses_while_customization_is_pending(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
) -> None:
    """Test the charger is not put through a sequence it never sees.

    Peblar's own web interface installs the customization package first and
    waits for the charger to come back before it touches the firmware.
    """
    await _async_offer_both_updates(hass, mock_peblar)

    with pytest.raises(HomeAssistantError) as excinfo:
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: "update.peblar_ev_charger_firmware"},
            blocking=True,
        )

    assert excinfo.value.translation_domain == DOMAIN
    assert excinfo.value.translation_key == "customization_update_first"
    mock_peblar.update.assert_not_called()


@pytest.mark.parametrize("init_integration", [Platform.UPDATE], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_install_firmware_asks_the_charger_for_fresh_versions(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
) -> None:
    """Test a customization published since the last poll still blocks firmware.

    Versions are polled once every two hours, and the charger answers from
    its own cache unless told not to, so the refusal would be decided on an
    answer that predates the very package it is meant to catch.
    """
    mock_peblar.current_versions.return_value = PeblarVersions.from_dict(
        {"Customization": "Peblar-1.9", "Firmware": "1.6.1+1+WL-1"}
    )
    mock_peblar.available_versions.return_value = PeblarVersions.from_dict(
        {"Customization": "Peblar-1.9", "Firmware": "1.6.2+1+WL-1"}
    )
    await hass.config_entries.async_reload(
        hass.config_entries.async_entries(DOMAIN)[0].entry_id
    )
    await hass.async_block_till_done()

    # Peblar publishes a customization package right after that poll.
    mock_peblar.available_versions.return_value = PeblarVersions.from_dict(
        {"Customization": "Peblar-2.0", "Firmware": "1.6.2+1+WL-1"}
    )

    with pytest.raises(HomeAssistantError) as excinfo:
        await hass.services.async_call(
            UPDATE_DOMAIN,
            SERVICE_INSTALL,
            {ATTR_ENTITY_ID: "update.peblar_ev_charger_firmware"},
            blocking=True,
        )

    assert excinfo.value.translation_key == "customization_update_first"
    mock_peblar.available_versions.assert_called_with(use_cache=False)
    mock_peblar.update.assert_not_called()


@pytest.mark.parametrize("init_integration", [Platform.UPDATE], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_install_firmware_after_the_customization_landed(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
) -> None:
    """Test the fresh answer counts the other way round too.

    The customization was installed on the charger since the last poll, so
    there is nothing left to wait for and the firmware may go ahead.
    """
    await _async_offer_both_updates(hass, mock_peblar)

    mock_peblar.current_versions.return_value = PeblarVersions.from_dict(
        {"Customization": "Peblar-1.9", "Firmware": "1.6.1+1+WL-1"}
    )

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: "update.peblar_ev_charger_firmware"},
        blocking=True,
    )

    mock_peblar.update.assert_called_once_with(package_type=PackageType.FIRMWARE)


async def _async_install(hass: HomeAssistant, package: str = "firmware") -> None:
    """Install an update the way a user does."""
    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: f"update.peblar_ev_charger_{package}"},
        blocking=True,
    )


async def _async_forget_the_version_reads_so_far(
    hass: HomeAssistant, mock_peblar: MagicMock
) -> None:
    """Start counting version reads from here.

    Setting up and installing both read the versions themselves, so let
    that settle first: what the tests below are after is the one extra read
    that following the charger through its reboot asks for.
    """
    await hass.async_block_till_done()
    mock_peblar.current_versions.reset_mock()


async def _async_poll(
    hass: HomeAssistant,
    freezer: FrozenDateTimeFactory,
    after: timedelta = timedelta(seconds=15),
) -> None:
    """Let the data coordinator run one poll, the given time from now."""
    freezer.tick(after)
    async_fire_time_changed(hass)
    await hass.async_block_till_done()


@pytest.mark.parametrize("init_integration", [Platform.UPDATE], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_versions_are_reread_once_the_charger_is_back(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a charger that just updated stops offering the update it took.

    Installing returns long before the charger is done, and versions are
    otherwise polled every two hours. Dropping off and coming back is what
    the charger does in between, and the data poll sees both moments.
    """
    meter = mock_peblar.rest_api.return_value.meter

    await _async_install(hass)
    await _async_forget_the_version_reads_so_far(hass, mock_peblar)

    # Still reachable, so the charger has not started rebooting yet.
    await _async_poll(hass, freezer)
    mock_peblar.current_versions.assert_not_called()

    # It goes away to install and reboot.
    meter.side_effect = PeblarConnectionError("Gone")
    await _async_poll(hass, freezer)
    await _async_poll(hass, freezer, after=timedelta(minutes=1))
    mock_peblar.current_versions.assert_not_called()

    # And comes back.
    meter.side_effect = None
    await _async_poll(hass, freezer)
    mock_peblar.current_versions.assert_called_once()


@pytest.mark.parametrize("init_integration", [Platform.UPDATE], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_versions_are_not_reread_without_an_install(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a charger rebooting on its own does not trigger a version read."""
    meter = mock_peblar.rest_api.return_value.meter

    await _async_forget_the_version_reads_so_far(hass, mock_peblar)

    meter.side_effect = PeblarConnectionError("Gone")
    await _async_poll(hass, freezer)
    await _async_poll(hass, freezer, after=timedelta(minutes=1))
    meter.side_effect = None
    await _async_poll(hass, freezer)

    mock_peblar.current_versions.assert_not_called()


@pytest.mark.parametrize("init_integration", [Platform.UPDATE], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_a_single_missed_poll_is_not_a_reboot(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a blip on the network does not end the wait.

    The charger is polled every ten seconds and may be downloading for
    hours, so it gets asked a great many times. Treating a single missed
    answer as a reboot would end the wait early, and the real reboot that
    follows would go unnoticed.
    """
    meter = mock_peblar.rest_api.return_value.meter

    await _async_install(hass)
    await _async_forget_the_version_reads_so_far(hass, mock_peblar)

    # One missed answer, then the charger is there again.
    meter.side_effect = PeblarConnectionError("Blip")
    await _async_poll(hass, freezer)
    meter.side_effect = None
    await _async_poll(hass, freezer)
    mock_peblar.current_versions.assert_not_called()

    # The actual reboot still gets noticed.
    meter.side_effect = PeblarConnectionError("Gone")
    await _async_poll(hass, freezer)
    await _async_poll(hass, freezer, after=timedelta(minutes=1))
    meter.side_effect = None
    await _async_poll(hass, freezer)
    mock_peblar.current_versions.assert_called_once()


@pytest.mark.parametrize("init_integration", [Platform.UPDATE], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_a_slow_update_is_still_picked_up(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a charger that takes its time downloading is still followed.

    The charger downloads the package before it reboots, so it can stay
    reachable for a long while after the install call returns. Peblar's own
    web interface allows three hours for that, far longer than the ten
    minutes it allows for the reboot itself.
    """
    meter = mock_peblar.rest_api.return_value.meter

    await _async_install(hass)
    await _async_forget_the_version_reads_so_far(hass, mock_peblar)

    # Half an hour of downloading, still reachable.
    await _async_poll(hass, freezer, after=timedelta(minutes=30))

    # Only now does it reboot, and come back.
    meter.side_effect = PeblarConnectionError("Gone")
    await _async_poll(hass, freezer)
    await _async_poll(hass, freezer, after=timedelta(minutes=1))
    meter.side_effect = None
    await _async_poll(hass, freezer)

    mock_peblar.current_versions.assert_called_once()


@pytest.mark.parametrize("init_integration", [Platform.UPDATE], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_waiting_stops_for_a_charger_that_never_returns(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the wait ends once the charger is overdue coming back.

    A charger that has gone down should be back within minutes. Waiting
    beyond that means the update did not go the way it should have, and
    whatever comes back later is not this update landing.
    """
    meter = mock_peblar.rest_api.return_value.meter

    await _async_install(hass)
    await _async_forget_the_version_reads_so_far(hass, mock_peblar)

    # The charger goes away, and stays away well past the ten minutes a
    # reboot is allowed to take.
    meter.side_effect = PeblarConnectionError("Gone")
    await _async_poll(hass, freezer)
    await _async_poll(hass, freezer, after=timedelta(minutes=1))
    await _async_poll(hass, freezer, after=timedelta(minutes=20))

    # Whatever comes back now is not this update landing.
    meter.side_effect = None
    await _async_poll(hass, freezer)

    mock_peblar.current_versions.assert_not_called()


@pytest.mark.parametrize("init_integration", [Platform.UPDATE], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_blips_do_not_extend_the_wait(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the charger does not get longer than it was given.

    A blip puts the wait back to waiting for the reboot to start, but on
    what is left of the original allowance. Handing out a fresh three hours
    each time would let a flaky network keep this going forever.
    """
    meter = mock_peblar.rest_api.return_value.meter

    await _async_install(hass)

    # Nearly out of time, then a blip.
    await _async_poll(hass, freezer, after=timedelta(hours=2, minutes=59))
    meter.side_effect = PeblarConnectionError("Blip")
    await _async_poll(hass, freezer)
    meter.side_effect = None
    await _async_poll(hass, freezer)

    # Past the three hours the charger was given from the start.
    await _async_poll(hass, freezer, after=timedelta(minutes=5))

    # So a reboot now is no longer this update landing, however long the
    # charger stays away for.
    await _async_forget_the_version_reads_so_far(hass, mock_peblar)
    meter.side_effect = PeblarConnectionError("Gone")
    await _async_poll(hass, freezer)
    meter.side_effect = None
    await _async_poll(hass, freezer, after=timedelta(minutes=1))

    mock_peblar.current_versions.assert_not_called()


@pytest.mark.parametrize("init_integration", [Platform.UPDATE], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_the_install_runs_on_until_the_new_versions_are_in(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the button does not come back before the versions it acts on.

    Calling the install done while the versions are still the ones from
    before it would put the button back next to the very package the
    charger has just taken.
    """
    entity_id = "update.peblar_ev_charger_firmware"
    meter = mock_peblar.rest_api.return_value.meter
    reading_versions = asyncio.Event()
    let_the_read_finish = asyncio.Event()

    async def _read_slowly() -> PeblarVersions:
        reading_versions.set()
        await let_the_read_finish.wait()
        return PeblarVersions.from_dict(
            {"Customization": "Peblar-1.9", "Firmware": "1.6.2+1+WL-1"}
        )

    await _async_install(hass)

    # It goes away to install and reboot.
    meter.side_effect = PeblarConnectionError("Gone")
    await _async_poll(hass, freezer)
    await _async_poll(hass, freezer, after=timedelta(minutes=1))

    # And comes back, on a charger that is slow to answer for its versions.
    mock_peblar.current_versions.side_effect = _read_slowly
    meter.side_effect = None
    freezer.tick(timedelta(seconds=15))
    async_fire_time_changed(hass)
    await reading_versions.wait()

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_IN_PROGRESS] is True

    let_the_read_finish.set()
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_IN_PROGRESS] is False


@pytest.mark.parametrize("init_integration", [Platform.UPDATE], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_a_second_install_is_refused_while_one_runs(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the charger is not handed a second package mid update.

    The install call returns while the charger is still downloading, so
    without saying so the button would be offered again straight away.
    Reporting the install as in progress is what makes the update
    component refuse a second one.
    """
    entity_id = "update.peblar_ev_charger_firmware"

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )
    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_IN_PROGRESS] is True

    # Once the charger is back, it can be asked again.
    meter = mock_peblar.rest_api.return_value.meter
    meter.side_effect = PeblarConnectionError("Gone")
    await _async_poll(hass, freezer)
    await _async_poll(hass, freezer, after=timedelta(minutes=1))
    meter.side_effect = None
    await _async_poll(hass, freezer)

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_IN_PROGRESS] is False


@pytest.mark.parametrize("init_integration", [Platform.UPDATE], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_the_button_returns_for_a_charger_that_never_came_back(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a charger that goes missing does not block installs forever."""
    entity_id = "update.peblar_ev_charger_firmware"

    await hass.services.async_call(
        UPDATE_DOMAIN,
        SERVICE_INSTALL,
        {ATTR_ENTITY_ID: entity_id},
        blocking=True,
    )

    meter = mock_peblar.rest_api.return_value.meter
    meter.side_effect = PeblarConnectionError("Gone")
    await _async_poll(hass, freezer)
    await _async_poll(hass, freezer, after=timedelta(minutes=1))

    # Well past the ten minutes a reboot is allowed to take.
    freezer.tick(timedelta(minutes=20))
    async_fire_time_changed(hass)
    await hass.async_block_till_done()

    state = hass.states.get(entity_id)
    assert state
    assert state.attributes[ATTR_IN_PROGRESS] is False
