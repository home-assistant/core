"""Tests for the iCloud config flow."""

from typing import Any
from unittest.mock import Mock, patch

from pyicloud.exceptions import PyiCloudFailedLoginException
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.icloud import async_remove_config_entry_device
from homeassistant.components.icloud.const import CONF_AUTO_DELETE, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from .conftest import MockAppleDevice
from .const import DEVICE_2, MOCK_CONFIG, USERNAME


@pytest.fixture(name="service_2fa")
def mock_controller_2fa_service():
    """Mock a successful 2fa service."""
    with patch(
        "homeassistant.components.icloud.account.PyiCloudService"
    ) as service_mock:
        service_mock.return_value.requires_2fa = True
        service_mock.return_value.requires_2sa = True
        service_mock.return_value.validate_2fa_code = Mock(return_value=True)
        service_mock.return_value.is_trusted_session = False
        yield service_mock


@pytest.fixture(name="service_2fa_failed")
def mock_controller_2fa_service_failed():
    """Mock a failed 2fa service."""
    with (
        patch(
            "homeassistant.components.icloud.account.PyiCloudService"
        ) as service_mock,
        patch(
            "homeassistant.components.icloud.config_flow.PyiCloudService", service_mock
        ),
    ):
        service_mock.side_effect = PyiCloudFailedLoginException("Invalid login")
        yield service_mock


@pytest.mark.usefixtures("service_2fa")
async def test_setup_2fa(hass: HomeAssistant) -> None:
    """Test that 2FA login triggers reauth flow."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.config_entries.flow.async_progress()

    await hass.config_entries.async_setup(config_entry.entry_id)
    # The first calendars/reminders fetch runs as a background task of the
    # config entry; waiting for it keeps the reauth flow count deterministic.
    await hass.async_block_till_done(wait_background_tasks=True)

    assert config_entry.state is ConfigEntryState.LOADED
    in_progress_flows = hass.config_entries.flow.async_progress()
    assert len(in_progress_flows) == 1
    assert in_progress_flows[0]["context"]["unique_id"] == config_entry.unique_id
    assert config_entry.runtime_data.api is not None


@pytest.mark.usefixtures("service_2fa_failed")
async def test_setup_password_failed(hass: HomeAssistant) -> None:
    """Test that invalid login triggers reauth flow."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.config_entries.flow.async_progress()

    await hass.config_entries.async_setup(config_entry.entry_id)
    # The first calendars/reminders fetch runs as a background task of the
    # config entry; waiting for it keeps the reauth flow count deterministic.
    await hass.async_block_till_done(wait_background_tasks=True)

    assert config_entry.state is ConfigEntryState.LOADED
    in_progress_flows = hass.config_entries.flow.async_progress()
    assert len(in_progress_flows) == 1
    assert in_progress_flows[0]["context"]["unique_id"] == config_entry.unique_id
    assert config_entry.runtime_data.api is None


@pytest.mark.usefixtures("service_2fa")
async def test_unique_id_set_on_setup(hass: HomeAssistant) -> None:
    """Test that unique_id is set on setup."""
    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=None
    )
    config_entry.add_to_hass(hass)

    assert config_entry.state is ConfigEntryState.NOT_LOADED

    await hass.config_entries.async_setup(config_entry.entry_id)
    # The first calendars/reminders fetch runs as a background task of the
    # config entry; waiting for it keeps the reauth flow count deterministic.
    await hass.async_block_till_done(wait_background_tasks=True)

    assert config_entry.unique_id == USERNAME
    assert config_entry.state is ConfigEntryState.LOADED


@pytest.mark.usefixtures("mock_icloud_service")
async def test_remove_config_entry_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    icloud_devices: list[MockAppleDevice],
) -> None:
    """Test a device can be removed only once iCloud stopped reporting it."""
    iphone = icloud_devices[0]
    icloud_devices.append(MockAppleDevice(DEVICE_2))

    config_entry = MockConfigEntry(
        domain=DOMAIN, data=MOCK_CONFIG, entry_id="test", unique_id=USERNAME
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    # The first calendars and reminders fetch runs as a background task of the
    # config entry; waiting for it keeps it from outliving the test.
    await hass.async_block_till_done(wait_background_tasks=True)

    iphone_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "device1"), config_entry.entry_id
    )
    ipad_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "device2"), config_entry.entry_id
    )
    assert iphone_entry is not None
    assert ipad_entry is not None

    # iCloud still reports the iPhone, so deleting it would only come back.
    assert not await async_remove_config_entry_device(hass, config_entry, iphone_entry)

    icloud_devices.remove(iphone)
    await hass.async_add_executor_job(config_entry.runtime_data.update_devices)
    await hass.async_block_till_done()

    assert await async_remove_config_entry_device(hass, config_entry, iphone_entry)
    assert not await async_remove_config_entry_device(hass, config_entry, ipad_entry)

    await hass.config_entries.async_unload(config_entry.entry_id)

    # Without a loaded account nothing can be confirmed as gone from iCloud.
    assert not await async_remove_config_entry_device(hass, config_entry, iphone_entry)


@pytest.mark.usefixtures("mock_icloud_service")
@pytest.mark.parametrize(
    ("options", "iphone_kept"),
    [
        pytest.param({CONF_AUTO_DELETE: True}, False, id="auto_delete_enabled"),
        pytest.param({}, True, id="auto_delete_disabled"),
    ],
)
async def test_auto_delete_removes_stale_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    icloud_devices: list[MockAppleDevice],
    options: dict[str, Any],
    iphone_kept: bool,
) -> None:
    """Test that a device Apple stopped reporting only goes when opted in.

    The account polls a list of what Apple currently reports, and that list
    can drop a device without saying so; the option turns that difference
    into a removal of the device and everything bound to it.
    """
    iphone = icloud_devices[0]
    icloud_devices.append(MockAppleDevice(DEVICE_2))

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        entry_id="test",
        unique_id=USERNAME,
        options=options,
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    # The first calendars and reminders fetch runs as a background task of the
    # config entry; waiting for it keeps it from outliving the test.
    await hass.async_block_till_done(wait_background_tasks=True)

    assert (
        device_registry.async_get_device_by_identifier(
            (DOMAIN, "device1"), config_entry.entry_id
        )
        is not None
    )
    assert entity_registry.async_get("sensor.iphone_battery") is not None

    icloud_devices.remove(iphone)
    await hass.async_add_executor_job(config_entry.runtime_data.update_devices)
    await hass.async_block_till_done()

    # The iPhone follows the option; the iPad Apple still reports is left
    # alone either way.
    iphone_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "device1"), config_entry.entry_id
    )
    iphone_battery = entity_registry.async_get("sensor.iphone_battery")

    assert ("device1" in config_entry.runtime_data.devices) is iphone_kept
    assert (iphone_entry is not None) is iphone_kept
    assert (iphone_battery is not None) is iphone_kept
    assert (hass.states.get("sensor.iphone_battery") is not None) is iphone_kept

    ipad_entry = device_registry.async_get_device_by_identifier(
        (DOMAIN, "device2"), config_entry.entry_id
    )
    assert ipad_entry is not None
    assert entity_registry.async_get("sensor.ipad_battery") is not None
