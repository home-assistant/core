"""Test the DuckDNS component."""

from datetime import timedelta
import logging
from unittest.mock import patch

from aiohttp import ClientError
import pytest

from homeassistant.components.duckdns.const import (
    ATTR_CONFIG_ENTRY,
    ATTR_TXT,
    DOMAIN,
    SERVICE_SET_TXT,
)
from homeassistant.components.duckdns.coordinator import BACKOFF_INTERVALS
from homeassistant.components.duckdns.helpers import UPDATE_URL
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_ACCESS_TOKEN, CONF_DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError, ServiceValidationError
from homeassistant.helpers import issue_registry as ir
from homeassistant.util.dt import utcnow

from .conftest import TEST_SUBDOMAIN, TEST_TOKEN

from tests.common import MockConfigEntry, async_fire_time_changed
from tests.test_util.aiohttp import AiohttpClientMocker

_LOGGER = logging.getLogger(__name__)


async def async_set_txt(hass: HomeAssistant, txt: str | None) -> None:
    """Set the txt record. Pass in None to remove it.

    This is a legacy helper method. Do not use it for new tests.
    """
    await hass.services.async_call(
        DOMAIN, SERVICE_SET_TXT, {ATTR_TXT: txt}, blocking=True
    )


@pytest.fixture
async def setup_duckdns(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
) -> None:
    """Fixture that sets up DuckDNS."""

    aioclient_mock.get(
        UPDATE_URL,
        params={"domains": TEST_SUBDOMAIN, "token": TEST_TOKEN},
        text="OK",
    )

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED


@pytest.mark.usefixtures("setup_duckdns")
async def test_setup(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker) -> None:
    """Test setup works if update passes."""
    aioclient_mock.get(
        UPDATE_URL,
        params={"domains": TEST_SUBDOMAIN, "token": TEST_TOKEN},
        text="OK",
    )

    assert aioclient_mock.call_count == 1

    async_fire_time_changed(hass, utcnow() + timedelta(minutes=5))
    await hass.async_block_till_done()
    assert aioclient_mock.call_count == 2


@pytest.mark.parametrize(
    "side_effect",
    [False, ClientError],
)
@pytest.mark.freeze_time
async def test_setup_backoff(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    side_effect: Exception | bool,
) -> None:
    """Test update fails with backoffs and recovers."""

    with patch(
        "homeassistant.components.duckdns.coordinator.update_duckdns",
        side_effect=[side_effect] * len(BACKOFF_INTERVALS),
    ) as client_mock:
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert config_entry.state is ConfigEntryState.SETUP_RETRY
        assert client_mock.call_count == 1

        tme = utcnow()
        await hass.async_block_till_done()

        _LOGGER.debug("Backoff")
        for idx in range(1, len(BACKOFF_INTERVALS)):
            tme += BACKOFF_INTERVALS[idx]
            async_fire_time_changed(hass, tme)
            await hass.async_block_till_done()

            assert client_mock.call_count == idx + 1

        client_mock.side_effect = None
        async_fire_time_changed(hass, tme)
        await hass.async_block_till_done()
        assert config_entry.state is ConfigEntryState.LOADED


@pytest.mark.usefixtures("setup_duckdns")
async def test_service_set_txt(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    issue_registry: ir.IssueRegistry,
) -> None:
    """Test set txt service call."""
    # Empty the fixture mock requests
    aioclient_mock.clear_requests()

    aioclient_mock.get(
        UPDATE_URL,
        params={"domains": TEST_SUBDOMAIN, "token": TEST_TOKEN, "txt": "some-txt"},
        text="OK",
    )

    assert aioclient_mock.call_count == 0

    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_TXT,
        {ATTR_TXT: "some-txt"},
        blocking=True,
    )
    assert aioclient_mock.call_count == 1

    assert issue_registry.async_get_issue(
        domain=DOMAIN,
        issue_id="deprecated_call_without_config_entry",
    )


@pytest.mark.usefixtures("setup_duckdns")
async def test_service_clear_txt(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test clear txt service call."""
    # Empty the fixture mock requests
    aioclient_mock.clear_requests()

    aioclient_mock.get(
        UPDATE_URL,
        params={
            "domains": TEST_SUBDOMAIN,
            "token": TEST_TOKEN,
            "txt": "",
            "clear": "true",
        },
        text="OK",
    )

    assert aioclient_mock.call_count == 0
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_TXT,
        blocking=True,
    )
    assert aioclient_mock.call_count == 1


@pytest.mark.parametrize(
    ("payload", "exception_msg"),
    [
        ({ATTR_CONFIG_ENTRY: "1234"}, "service_config_entry_not_found"),
        (None, "entry_not_selected"),
    ],
)
@pytest.mark.usefixtures("setup_duckdns")
async def test_service_exceptions(
    hass: HomeAssistant,
    payload: dict[str, str] | None,
    exception_msg: str,
) -> None:
    """Test config entry select exceptions."""
    MockConfigEntry(
        domain=DOMAIN,
        title=f"{TEST_SUBDOMAIN}.duckdns.org",
        data={
            CONF_DOMAIN: TEST_SUBDOMAIN,
            CONF_ACCESS_TOKEN: TEST_TOKEN,
        },
        entry_id="67890",
    ).add_to_hass(hass)

    with pytest.raises(ServiceValidationError) as e:
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_TXT,
            payload,
            blocking=True,
        )
    assert e.value.translation_key == exception_msg


@pytest.mark.parametrize(
    ("side_effect", "exception_msg"),
    [
        (False, "update_failed"),
        (ClientError, "connection_error"),
    ],
)
@pytest.mark.usefixtures("setup_duckdns")
async def test_service_request_exception(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    side_effect: Exception | bool,
    exception_msg: str,
) -> None:
    """Test service request exception."""

    with (
        patch(
            "homeassistant.components.duckdns.services.update_duckdns",
            side_effect=[side_effect],
        ),
        pytest.raises(HomeAssistantError) as e,
    ):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_SET_TXT,
            {ATTR_CONFIG_ENTRY: config_entry.entry_id},
            blocking=True,
        )
    assert e.value.translation_key == exception_msg


@pytest.mark.usefixtures("setup_duckdns")
async def test_service_select_entry(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """Test config entry selection."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title=f"{TEST_SUBDOMAIN}.duckdns.org",
        data={
            CONF_DOMAIN: TEST_SUBDOMAIN,
            CONF_ACCESS_TOKEN: TEST_TOKEN,
        },
        entry_id="67890",
    )
    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.LOADED

    # Empty the fixture mock requests
    aioclient_mock.clear_requests()

    aioclient_mock.get(
        UPDATE_URL,
        params={
            "domains": TEST_SUBDOMAIN,
            "token": TEST_TOKEN,
            "txt": "",
            "clear": "true",
        },
        text="OK",
    )

    assert aioclient_mock.call_count == 0
    await hass.services.async_call(
        DOMAIN,
        SERVICE_SET_TXT,
        {ATTR_CONFIG_ENTRY: "67890"},
        blocking=True,
    )
    assert aioclient_mock.call_count == 1


async def test_load_unload(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    aioclient_mock: AiohttpClientMocker,
) -> None:
    """Test loading and unloading of the config entry."""

    aioclient_mock.get(
        UPDATE_URL,
        params={"domains": TEST_SUBDOMAIN, "token": TEST_TOKEN},
        text="OK",
    )
    config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    entries = hass.config_entries.async_entries(DOMAIN)
    assert len(entries) == 1

    assert config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    assert config_entry.state is ConfigEntryState.NOT_LOADED
