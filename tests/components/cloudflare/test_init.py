"""Test the Cloudflare integration."""

from datetime import timedelta
from unittest.mock import MagicMock, patch

from freezegun.api import FrozenDateTimeFactory
import pycfdns
import pytest

from homeassistant.components.cloudflare.const import (
    CONF_RECORDS,
    DEFAULT_UPDATE_INTERVAL,
    DOMAIN,
    SERVICE_UPDATE_RECORDS,
)
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.core import HomeAssistant

from . import ENTRY_CONFIG, init_integration
from .conftest import LOCATION_PATCH_TARGET

from tests.common import MockConfigEntry, async_fire_time_changed


@pytest.mark.parametrize(
    "side_effect",
    [pycfdns.ComunicationException()],
)
async def test_async_setup_raises_entry_not_ready(
    hass: HomeAssistant, cfupdate: MagicMock, side_effect: Exception
) -> None:
    """Test that it throws ConfigEntryNotReady when exception occurs during setup."""
    instance = cfupdate.return_value

    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_CONFIG)
    entry.add_to_hass(hass)

    instance.list_zones.side_effect = side_effect
    await hass.config_entries.async_setup(entry.entry_id)

    assert entry.state is ConfigEntryState.SETUP_RETRY


async def test_async_setup_raises_entry_auth_failed(
    hass: HomeAssistant, cfupdate: MagicMock
) -> None:
    """Test that it throws ConfigEntryAuthFailed when exception occurs during setup."""
    instance = cfupdate.return_value

    entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_CONFIG)
    entry.add_to_hass(hass)

    instance.list_zones.side_effect = pycfdns.AuthenticationException()
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.SETUP_ERROR

    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1

    flow = flows[0]
    assert flow["step_id"] == "reauth_confirm"
    assert flow["handler"] == DOMAIN

    assert "context" in flow
    assert flow["context"]["source"] == SOURCE_REAUTH
    assert flow["context"]["entry_id"] == entry.entry_id


@pytest.mark.usefixtures("location_info")
async def test_unload_entry(hass: HomeAssistant, cfupdate: MagicMock) -> None:
    """Test successful unload of entry."""
    entry = await init_integration(hass)

    assert len(hass.config_entries.async_entries(DOMAIN)) == 1
    assert entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.usefixtures("location_info")
async def test_integration_services(
    hass: HomeAssistant, cfupdate: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Test integration services."""
    instance = cfupdate.return_value

    entry = await init_integration(hass)
    assert entry.state is ConfigEntryState.LOADED

    assert len(instance.update_dns_record.mock_calls) == 2
    instance.update_dns_record.reset_mock()

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_RECORDS,
        {},
        blocking=True,
    )
    await hass.async_block_till_done()

    assert len(instance.update_dns_record.mock_calls) == 2
    assert "All target records are up to date" not in caplog.text


@pytest.mark.usefixtures("location_info")
async def test_integration_services_with_issue(
    hass: HomeAssistant, cfupdate: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Test integration services with issue."""
    instance = cfupdate.return_value

    entry = await init_integration(hass)
    assert entry.state is ConfigEntryState.LOADED

    assert len(instance.update_dns_record.mock_calls) == 2
    instance.update_dns_record.reset_mock()

    with patch(LOCATION_PATCH_TARGET, return_value=None):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_UPDATE_RECORDS,
            {},
            blocking=True,
        )

    instance.update_dns_record.assert_not_called()
    assert "Could not get external IPv4 address" in caplog.text


@pytest.mark.usefixtures("location_info")
async def test_integration_services_with_nonexisting_record(
    hass: HomeAssistant, cfupdate: MagicMock, caplog: pytest.LogCaptureFixture
) -> None:
    """Test integration services."""
    instance = cfupdate.return_value

    entry = await init_integration(
        hass, data={**ENTRY_CONFIG, CONF_RECORDS: ["nonexisting.example.com"]}
    )
    assert entry.state is ConfigEntryState.LOADED

    await hass.services.async_call(
        DOMAIN,
        SERVICE_UPDATE_RECORDS,
        {},
        blocking=True,
    )
    await hass.async_block_till_done()

    instance.update_dns_record.assert_not_called()
    assert "All target records are up to date" in caplog.text


@pytest.mark.usefixtures("location_info")
async def test_integration_update_interval(
    hass: HomeAssistant,
    cfupdate: MagicMock,
    caplog: pytest.LogCaptureFixture,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test integration update interval."""
    instance = cfupdate.return_value

    entry = await init_integration(hass)
    assert entry.state is ConfigEntryState.LOADED

    freezer.tick(timedelta(minutes=DEFAULT_UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(instance.list_dns_records.mock_calls) == 2
    assert len(instance.update_dns_record.mock_calls) == 4
    assert "All target records are up to date" not in caplog.text

    instance.list_dns_records.side_effect = pycfdns.AuthenticationException()
    freezer.tick(timedelta(minutes=DEFAULT_UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(instance.list_dns_records.mock_calls) == 3
    assert len(instance.update_dns_record.mock_calls) == 4

    instance.list_dns_records.side_effect = pycfdns.ComunicationException()
    freezer.tick(timedelta(minutes=DEFAULT_UPDATE_INTERVAL))
    async_fire_time_changed(hass)
    await hass.async_block_till_done(wait_background_tasks=True)
    assert len(instance.list_dns_records.mock_calls) == 4
    assert len(instance.update_dns_record.mock_calls) == 4
