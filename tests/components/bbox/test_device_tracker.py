"""Tests for the Bbox device tracker platform."""

from datetime import timedelta

from aiohttp import ClientConnectionError
from freezegun.api import FrozenDateTimeFactory
from probatio import Invalid
import pytest
from pytest_homeassistant.test_util.aiohttp import AiohttpClientMocker

from homeassistant.components.bbox.const import DEFAULT_HOST
from homeassistant.components.bbox.device_tracker import (
    PLATFORM_SCHEMA,
    BboxDeviceScanner,
)
from homeassistant.components.device_tracker.const import (
    DOMAIN as DEVICE_TRACKER_DOMAIN,
)
from homeassistant.const import CONF_HOST, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from .const import (
    GUEST_NETWORK_HOSTS,
    HOST,
    HOSTS_RESPONSE,
    HOSTS_URL,
    MAIN_NETWORK_HOSTS,
    PASSWORD,
)

ACTIVE_HOST = MAIN_NETWORK_HOSTS[0]
ACTIVE_MAC = ACTIVE_HOST["macaddress"]


def test_platform_schema_requires_password() -> None:
    """Test that the platform is not configurable without a password."""
    with pytest.raises(Invalid):
        PLATFORM_SCHEMA({"platform": "bbox"})


def test_platform_schema_defaults() -> None:
    """Test the platform defaults for host and verify_ssl."""
    config = PLATFORM_SCHEMA({"platform": "bbox", "password": PASSWORD})
    assert config[CONF_HOST] == DEFAULT_HOST
    assert config[CONF_VERIFY_SSL] is True


def test_platform_schema_verify_ssl_disabled() -> None:
    """Test that verify_ssl can be disabled, e.g. for a numeric host."""
    config = PLATFORM_SCHEMA(
        {"platform": "bbox", "password": PASSWORD, "verify_ssl": False}
    )
    assert config[CONF_VERIFY_SSL] is False


async def test_scanner(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that the scanner tracks the active devices of the main network."""
    aioclient_mock.get(HOSTS_URL, json=HOSTS_RESPONSE)
    scanner = await hass.async_add_executor_job(BboxDeviceScanner, hass, HOST, PASSWORD)
    assert scanner.success_init is True
    devices = await hass.async_add_executor_job(scanner.scan_devices)
    assert devices == [ACTIVE_MAC]
    name = await hass.async_add_executor_job(scanner.get_device_name, ACTIVE_MAC)
    assert name == ACTIVE_HOST["hostname"]
    assert scanner.get_device_name("aa:bb:cc:dd:ee:99") is None


async def test_scanner_skips_malformed_entries(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that malformed device entries are skipped, not fatal."""
    malformed_response = [
        {
            "hosts": {
                "list": [
                    {"hostname": "Ghost"},  # no active/macaddress
                    {"active": 1},  # active but no macaddress
                    ACTIVE_HOST,
                ]
            }
        }
    ]
    aioclient_mock.get(HOSTS_URL, json=malformed_response)
    scanner = await hass.async_add_executor_job(BboxDeviceScanner, hass, HOST, PASSWORD)
    assert scanner.success_init is True
    devices = await hass.async_add_executor_job(scanner.scan_devices)
    assert devices == [ACTIVE_MAC]


async def test_scanner_is_throttled(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that the scanner repeats the fetch only after the throttle."""
    freezer.move_to("2026-11-11T15:00:00+00:00")
    aioclient_mock.get(HOSTS_URL, json=HOSTS_RESPONSE)
    scanner = await hass.async_add_executor_job(BboxDeviceScanner, hass, HOST, PASSWORD)
    assert aioclient_mock.call_count == 1

    await hass.async_add_executor_job(scanner.scan_devices)
    assert aioclient_mock.call_count == 1

    freezer.tick(timedelta(seconds=61))
    await hass.async_add_executor_job(scanner.scan_devices)
    assert aioclient_mock.call_count == 2


async def test_scanner_clears_cache_on_failure(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    freezer: FrozenDateTimeFactory,
) -> None:
    """Test that a failed scan drops the cached list instead of replaying it."""
    freezer.move_to("2026-11-11T15:00:00+00:00")
    aioclient_mock.get(HOSTS_URL, json=HOSTS_RESPONSE)
    scanner = await hass.async_add_executor_job(BboxDeviceScanner, hass, HOST, PASSWORD)
    devices = await hass.async_add_executor_job(scanner.scan_devices)
    assert devices == [ACTIVE_MAC]

    aioclient_mock.clear_requests()
    aioclient_mock.get(HOSTS_URL, exc=ClientConnectionError("boom"))
    freezer.tick(timedelta(seconds=61))
    devices = await hass.async_add_executor_job(scanner.scan_devices)
    assert devices == []
    assert scanner.get_device_name(ACTIVE_MAC) is None


async def test_scanner_connection_error(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that the scanner reports an unsuccessful init when unreachable."""
    aioclient_mock.get(HOSTS_URL, exc=ClientConnectionError("boom"))
    scanner = await hass.async_add_executor_job(BboxDeviceScanner, hass, HOST, PASSWORD)
    assert scanner.success_init is False
    assert scanner.last_results == []
    assert scanner.get_device_name(ACTIVE_MAC) is None


@pytest.mark.usefixtures("mock_device_tracker_conf")
async def test_setup_platform(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test that the legacy platform sets up and sees the active devices."""
    aioclient_mock.get(HOSTS_URL, json=HOSTS_RESPONSE)
    assert await async_setup_component(
        hass,
        DEVICE_TRACKER_DOMAIN,
        {DEVICE_TRACKER_DOMAIN: {"platform": "bbox", "password": PASSWORD}},
    )
    await hass.async_block_till_done()

    tracked_state = hass.states.get(f"device_tracker.{ACTIVE_HOST['hostname'].lower()}")
    assert tracked_state is not None
    assert tracked_state.state == "home"
    # Inactive and guest network devices are not tracked.
    assert (
        hass.states.get(f"device_tracker.{MAIN_NETWORK_HOSTS[1]['hostname'].lower()}")
        is None
    )
    assert (
        hass.states.get(f"device_tracker.{GUEST_NETWORK_HOSTS[0]['hostname'].lower()}")
        is None
    )
