"""Tests for the Peblar update platform."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
from peblar import PackageType, PeblarConnectionError, PeblarVersions
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.peblar.const import DOMAIN
from homeassistant.components.update import DOMAIN as UPDATE_DOMAIN, SERVICE_INSTALL
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
async def test_versions_are_reread_once_the_charger_is_back(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a charger that just updated stops offering the update it took.

    Installing returns long before the charger is done, and versions are
    otherwise polled every two hours. Dropping off and coming back is what
    the charger does in between, and the data poll sees both moments.
    """
    runtime_data = mock_config_entry.runtime_data
    data_coordinator = runtime_data.data_coordinator

    runtime_data.version_coordinator.async_refresh_after_restart()
    mock_peblar.current_versions.reset_mock()

    # Still reachable, so the charger has not started rebooting yet.
    data_coordinator.async_set_updated_data(data_coordinator.data)
    await hass.async_block_till_done()
    mock_peblar.current_versions.assert_not_called()

    # It goes away to install and reboot.
    data_coordinator.async_set_update_error(PeblarConnectionError("Gone"))
    await hass.async_block_till_done()
    mock_peblar.current_versions.assert_not_called()

    # And comes back.
    data_coordinator.async_set_updated_data(data_coordinator.data)
    await hass.async_block_till_done()
    mock_peblar.current_versions.assert_called_once()


@pytest.mark.parametrize("init_integration", [Platform.UPDATE], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_versions_are_not_reread_without_an_install(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a charger rebooting on its own does not trigger a version read."""
    data_coordinator = mock_config_entry.runtime_data.data_coordinator
    mock_peblar.current_versions.reset_mock()

    data_coordinator.async_set_update_error(PeblarConnectionError("Gone"))
    await hass.async_block_till_done()
    data_coordinator.async_set_updated_data(data_coordinator.data)
    await hass.async_block_till_done()

    mock_peblar.current_versions.assert_not_called()


@pytest.mark.parametrize("init_integration", [Platform.UPDATE], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_a_slow_update_is_still_picked_up(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test a charger that takes its time downloading is still followed.

    The charger downloads the package before it reboots, so it can stay
    reachable for a long while after the install call returns. Peblar's own
    web interface allows three hours for that, far longer than the ten
    minutes it allows for the reboot itself.
    """
    runtime_data = mock_config_entry.runtime_data
    data_coordinator = runtime_data.data_coordinator

    with patch.object(
        runtime_data.version_coordinator, "async_request_refresh"
    ) as mock_refresh:
        runtime_data.version_coordinator.async_refresh_after_restart()

        # Half an hour of downloading, still reachable.
        freezer.tick(timedelta(minutes=30))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        # Only now does it reboot, and come back.
        data_coordinator.async_set_update_error(PeblarConnectionError("Gone"))
        await hass.async_block_till_done()
        data_coordinator.async_set_updated_data(data_coordinator.data)
        await hass.async_block_till_done()

        mock_refresh.assert_called_once()


@pytest.mark.parametrize("init_integration", [Platform.UPDATE], indirect=True)
@pytest.mark.usefixtures("init_integration")
async def test_waiting_stops_for_a_charger_that_never_returns(
    hass: HomeAssistant,
    mock_peblar: MagicMock,
    mock_config_entry: MockConfigEntry,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test the wait ends once the charger is overdue coming back.

    A charger that has gone down should be back within minutes. Waiting
    beyond that means the update did not go the way it should have, and
    whatever comes back later is not this update landing.
    """
    runtime_data = mock_config_entry.runtime_data
    data_coordinator = runtime_data.data_coordinator

    with patch.object(
        runtime_data.version_coordinator, "async_request_refresh"
    ) as mock_refresh:
        runtime_data.version_coordinator.async_refresh_after_restart()

        # The charger goes away, and stays away.
        mock_peblar.rest_api.return_value.meter.side_effect = PeblarConnectionError(
            "Gone"
        )
        freezer.tick(timedelta(seconds=15))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()
        assert not data_coordinator.last_update_success

        # Well past the ten minutes a reboot is allowed to take.
        freezer.tick(timedelta(minutes=20))
        async_fire_time_changed(hass)
        await hass.async_block_till_done()

        # Whatever comes back now is not this update landing.
        mock_peblar.rest_api.return_value.meter.side_effect = None
        data_coordinator.async_set_updated_data(data_coordinator.data)
        await hass.async_block_till_done()

        mock_refresh.assert_not_called()
