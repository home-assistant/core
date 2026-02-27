"""Test initialization for dk_fuelprices."""

from types import SimpleNamespace
from typing import cast
from unittest.mock import AsyncMock, patch

from homeassistant.components.dk_fuelprices import (
    _update_listener,
    async_remove_config_entry_device,
    async_setup_entry,
    async_unload_entry,
    remove_stale_devices,
)
from homeassistant.components.dk_fuelprices.const import (
    CONF_COMPANY,
    CONF_STATION,
    DOMAIN,
)
from homeassistant.config_entries import ConfigSubentryData
from homeassistant.const import CONF_API_KEY
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers.device_registry import DeviceEntry

from .conftest import TEST_API_KEY, TEST_COMPANY, TEST_STATION

from tests.common import MockConfigEntry


async def test_update_listener_schedules_reload(hass: HomeAssistant) -> None:
    """Test update listener schedules an entry reload."""
    config_entry = MockConfigEntry(domain=DOMAIN, data={CONF_API_KEY: TEST_API_KEY})
    config_entry.add_to_hass(hass)

    with patch.object(hass.config_entries, "async_schedule_reload") as reload_mock:
        await _update_listener(hass, config_entry)

    reload_mock.assert_called_once_with(config_entry.entry_id)


async def test_async_setup_entry_creates_coordinator(hass: HomeAssistant) -> None:
    """Test setup creates coordinators from subentries."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data={CONF_API_KEY: TEST_API_KEY},
        subentries_data=[
            ConfigSubentryData(
                subentry_type="station",
                title="Station",
                unique_id=f"{TEST_COMPANY}_{TEST_STATION['id']}",
                data={
                    CONF_COMPANY: TEST_COMPANY,
                    CONF_STATION: TEST_STATION,
                },
            )
        ],
    )
    config_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.dk_fuelprices.APIClient") as mock_api_client,
        patch.object(
            hass.config_entries, "async_forward_entry_setups", return_value=True
        ) as forward_mock,
    ):
        coordinator = mock_api_client.return_value
        coordinator.async_config_entry_first_refresh = AsyncMock()

        assert await async_setup_entry(hass, config_entry) is True
        assert len(config_entry.runtime_data) == 1
        coordinator.async_config_entry_first_refresh.assert_awaited_once()
        forward_mock.assert_awaited_once()


async def test_async_setup_entry_returns_false_without_api_key(
    hass: HomeAssistant,
) -> None:
    """Test setup fails when API key is missing."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data={},
        subentries_data=[
            ConfigSubentryData(
                subentry_type="station",
                title="Station",
                unique_id="station_1",
                data={
                    CONF_COMPANY: TEST_COMPANY,
                    CONF_STATION: TEST_STATION,
                },
            )
        ],
    )
    config_entry.add_to_hass(hass)

    with patch("homeassistant.components.dk_fuelprices.APIClient") as mock_api_client:
        assert await async_setup_entry(hass, config_entry) is False
        mock_api_client.assert_not_called()


async def test_async_remove_config_entry_device(hass: HomeAssistant) -> None:
    """Test config entry device removal decision with subentry identifiers."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data={CONF_API_KEY: TEST_API_KEY},
        subentries_data=[
            ConfigSubentryData(
                subentry_type="station",
                title="Station",
                unique_id="station_1",
                data={},
            )
        ],
    )
    entry.add_to_hass(hass)
    subentry_id = next(iter(entry.subentries))

    linked_device = SimpleNamespace(identifiers={(DOMAIN, subentry_id)})
    unlinked_device = SimpleNamespace(identifiers={(DOMAIN, "station_2")})

    assert (
        await async_remove_config_entry_device(
            hass, entry, cast(DeviceEntry, linked_device)
        )
        is False
    )
    assert (
        await async_remove_config_entry_device(
            hass, entry, cast(DeviceEntry, unlinked_device)
        )
        is True
    )


async def test_remove_stale_devices(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test stale devices are removed from the config entry."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data={CONF_API_KEY: TEST_API_KEY},
        subentries_data=[
            ConfigSubentryData(
                subentry_type="station",
                title="Valid",
                unique_id="valid_device",
                data={},
            )
        ],
    )
    config_entry.add_to_hass(hass)

    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "valid_device")},
        name="Valid device",
    )
    device_registry.async_get_or_create(
        config_entry_id=config_entry.entry_id,
        identifiers={(DOMAIN, "stale_device")},
        name="Stale device",
    )

    devices = {"valid": SimpleNamespace(deviceid="valid_device")}
    remove_stale_devices(hass, config_entry, devices)

    entries = dr.async_entries_for_config_entry(device_registry, config_entry.entry_id)
    identifiers = {next(iter(device.identifiers))[1] for device in entries}
    assert identifiers == {"valid_device"}


async def test_async_setup_and_unload_entry(hass: HomeAssistant) -> None:
    """Test setup/unload forwards and removes integration runtime data."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        version=1,
        data={CONF_API_KEY: TEST_API_KEY},
        subentries_data=[
            ConfigSubentryData(
                subentry_type="station",
                title="Station",
                unique_id="station_1",
                data={
                    CONF_COMPANY: TEST_COMPANY,
                    CONF_STATION: TEST_STATION,
                },
            )
        ],
    )
    config_entry.add_to_hass(hass)

    with (
        patch("homeassistant.components.dk_fuelprices.APIClient") as mock_api_client,
        patch.object(
            hass.config_entries, "async_forward_entry_setups", return_value=True
        ),
        patch.object(hass.config_entries, "async_unload_platforms", return_value=True),
    ):
        mock_api_client.return_value.async_config_entry_first_refresh = AsyncMock()
        assert await async_setup_entry(hass, config_entry) is True
        assert len(config_entry.runtime_data) == 1

        assert await async_unload_entry(hass, config_entry) is True
        assert config_entry.runtime_data == {}
