"""Test account link services."""

import asyncio
from collections.abc import Generator
import logging
from time import time
from unittest.mock import AsyncMock, Mock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.cloud import account_link
from homeassistant.components.cloud.const import DATA_CLOUD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import config_entry_oauth2_flow
from homeassistant.util.dt import utcnow

from tests.common import MockConfigEntry, async_fire_time_changed, mock_platform

TEST_DOMAIN = "oauth2_test"


@pytest.fixture
def flow_handler(
    hass: HomeAssistant,
) -> Generator[type[config_entry_oauth2_flow.AbstractOAuth2FlowHandler]]:
    """Return a registered config flow."""

    mock_platform(hass, f"{TEST_DOMAIN}.config_flow")

    class TestFlowHandler(config_entry_oauth2_flow.AbstractOAuth2FlowHandler):
        """Test flow handler."""

        DOMAIN = TEST_DOMAIN

        @property
        def logger(self) -> logging.Logger:
            """Return logger."""
            return logging.getLogger(__name__)

    with patch.dict(config_entries.HANDLERS, {TEST_DOMAIN: TestFlowHandler}):
        yield TestFlowHandler


async def test_setup_provide_implementation(hass: HomeAssistant) -> None:
    """Test that we provide implementations."""
    legacy_entry = MockConfigEntry(
        domain="legacy",
        version=1,
        data={"auth_implementation": "cloud"},
    )
    none_cloud_entry = MockConfigEntry(
        domain="no_cloud",
        version=1,
        data={"auth_implementation": "somethingelse"},
    )
    none_cloud_entry.add_to_hass(hass)
    legacy_entry.add_to_hass(hass)
    account_link.async_setup(hass)

    with (
        patch(
            "homeassistant.components.cloud.account_link._get_services",
            return_value=[
                {"service": "test", "min_version": "0.1.0"},
                {"service": "too_new", "min_version": "1000000.0.0"},
                {"service": "dev", "min_version": "2022.9.0"},
                {
                    "service": "deprecated",
                    "min_version": "0.1.0",
                    "accepts_new_authorizations": False,
                },
                {
                    "service": "legacy",
                    "min_version": "0.1.0",
                    "accepts_new_authorizations": False,
                },
                {
                    "service": "no_cloud",
                    "min_version": "0.1.0",
                    "accepts_new_authorizations": False,
                },
            ],
        ),
        patch(
            "homeassistant.components.cloud.account_link.HA_VERSION",
            "2022.9.0.dev20220817",
        ),
    ):
        assert (
            await config_entry_oauth2_flow.async_get_implementations(
                hass, "non_existing"
            )
            == {}
        )
        assert (
            await config_entry_oauth2_flow.async_get_implementations(hass, "too_new")
            == {}
        )
        assert (
            await config_entry_oauth2_flow.async_get_implementations(hass, "deprecated")
            == {}
        )
        assert (
            await config_entry_oauth2_flow.async_get_implementations(hass, "no_cloud")
            == {}
        )

        implementations = await config_entry_oauth2_flow.async_get_implementations(
            hass, "test"
        )

        legacy_implementations = (
            await config_entry_oauth2_flow.async_get_implementations(hass, "legacy")
        )

        dev_implementations = await config_entry_oauth2_flow.async_get_implementations(
            hass, "dev"
        )

    assert "cloud" in implementations
    assert implementations["cloud"].domain == "cloud"
    assert implementations["cloud"].service == "test"
    assert implementations["cloud"].hass is hass

    assert "cloud" in legacy_implementations
    assert legacy_implementations["cloud"].domain == "cloud"
    assert legacy_implementations["cloud"].service == "legacy"
    assert legacy_implementations["cloud"].hass is hass

    assert "cloud" in dev_implementations
    assert dev_implementations["cloud"].domain == "cloud"
    assert dev_implementations["cloud"].service == "dev"
    assert dev_implementations["cloud"].hass is hass


async def test_get_services_cached(hass: HomeAssistant) -> None:
    """Test that we cache services."""
    hass.data[DATA_CLOUD] = None

    services = 1

    with (
        patch.object(account_link, "CACHE_TIMEOUT", 0),
        patch(
            "hass_nabucasa.account_link.async_fetch_available_services",
            side_effect=lambda _: services,
        ) as mock_fetch,
    ):
        assert await account_link._get_services(hass) == 1

        services = 2

        assert len(mock_fetch.mock_calls) == 1
        assert await account_link._get_services(hass) == 1

        services = 3
        hass.data.pop(account_link.DATA_SERVICES)
        assert await account_link._get_services(hass) == 3

        services = 4
        async_fire_time_changed(hass, utcnow())
        await hass.async_block_till_done()

        # Check cache purged
        assert await account_link._get_services(hass) == 4


async def test_get_services_error(hass: HomeAssistant) -> None:
    """Test that we cache services."""
    hass.data[DATA_CLOUD] = None

    with (
        patch.object(account_link, "CACHE_TIMEOUT", 0),
        patch(
            "hass_nabucasa.account_link.async_fetch_available_services",
            side_effect=TimeoutError,
        ),
    ):
        assert await account_link._get_services(hass) == []
        assert account_link.DATA_SERVICES not in hass.data


@pytest.mark.usefixtures("current_request_with_host")
async def test_implementation(
    hass: HomeAssistant,
    flow_handler: type[config_entry_oauth2_flow.AbstractOAuth2FlowHandler],
) -> None:
    """Test Cloud OAuth2 implementation."""
    hass.data[DATA_CLOUD] = None

    impl = account_link.CloudOAuth2Implementation(hass, "test")
    assert impl.name == "Home Assistant Cloud"
    assert impl.domain == "cloud"

    flow_handler.async_register_implementation(hass, impl)

    flow_finished = asyncio.Future()

    helper = Mock(
        async_get_authorize_url=AsyncMock(return_value="http://example.com/auth"),
        async_get_tokens=Mock(return_value=flow_finished),
    )

    with patch(
        "hass_nabucasa.account_link.AuthorizeAccountHelper", return_value=helper
    ):
        result = await hass.config_entries.flow.async_init(
            TEST_DOMAIN, context={"source": config_entries.SOURCE_USER}
        )

    assert result["type"] is FlowResultType.EXTERNAL_STEP
    assert result["url"] == "http://example.com/auth"

    flow_finished.set_result(
        {
            "refresh_token": "mock-refresh",
            "access_token": "mock-access",
            "expires_in": 10,
            "token_type": "bearer",
        }
    )
    await hass.async_block_till_done()

    # Flow finished!
    result = await hass.config_entries.flow.async_configure(result["flow_id"])

    assert result["data"]["auth_implementation"] == "cloud"

    expires_at = result["data"]["token"].pop("expires_at")
    assert round(expires_at - time()) == 10

    assert result["data"]["token"] == {
        "refresh_token": "mock-refresh",
        "access_token": "mock-access",
        "token_type": "bearer",
        "expires_in": 10,
    }

    entry = hass.config_entries.async_entries(TEST_DOMAIN)[0]

    assert (
        await config_entry_oauth2_flow.async_get_config_entry_implementation(
            hass, entry
        )
        is impl
    )
