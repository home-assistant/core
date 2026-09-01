"""Common fixtures for the Zonneplan tests."""

from collections.abc import Generator
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
from pyzonneplan import Account, ConsumerPrices, OtpChallenge, Token, Zonneplan
from pyzonneplan.const import PriceChart

from homeassistant.components.zonneplan.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_TOKEN

from tests.common import MockConfigEntry, load_json_object_fixture

MOCK_EMAIL = "user@example.com"
MOCK_USER_INPUT = {CONF_EMAIL: MOCK_EMAIL}
MOCK_ACCOUNT = Account.from_dict(load_json_object_fixture("get_account.json", DOMAIN))


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.zonneplan.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture(autouse=True)
def mock_zonneplan_client() -> Generator[AsyncMock]:
    """Mock the Zonneplan client."""
    client = AsyncMock(Zonneplan)
    client.token = Token(
        access_token="mock-access-token",
        refresh_token="mock-refresh-token",
        expires_at=datetime(2030, 1, 1, tzinfo=UTC),
    )
    client.async_request_otp.return_value = OtpChallenge(
        auth_session="mock-auth-session",
        code_verifier="mock-code-verifier",
        email=MOCK_EMAIL,
    )
    client.async_submit_otp.return_value = Token(
        access_token="mock-access-token",
        refresh_token="mock-refresh-token",
        expires_at=datetime(2030, 1, 1, tzinfo=UTC),
    )
    client.async_get_account.return_value = MOCK_ACCOUNT

    prices_by_chart = {
        PriceChart.ELECTRICITY_HOURLY: ConsumerPrices.from_dict(
            load_json_object_fixture(
                "get_consumer_prices_electricity_hourly.json", DOMAIN
            )
        ),
        PriceChart.GAS_DAILY: ConsumerPrices.from_dict(
            load_json_object_fixture("get_consumer_prices_gas_daily.json", DOMAIN)
        ),
    }
    client.async_get_consumer_prices.side_effect = lambda chart: prices_by_chart[chart]

    with (
        patch("homeassistant.components.zonneplan.Zonneplan", return_value=client),
        patch(
            "homeassistant.components.zonneplan.config_flow.Zonneplan",
            return_value=client,
        ),
    ):
        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title=MOCK_EMAIL,
        unique_id=MOCK_ACCOUNT.user_account.uuid,
        entry_id="01JXZKYZ00XZKYZ00XZKYZ00XZ",
        data={
            CONF_EMAIL: MOCK_EMAIL,
            CONF_TOKEN: Token(
                access_token="mock-access-token",
                refresh_token="mock-refresh-token",
                expires_at=datetime(2030, 1, 1, tzinfo=UTC),
            ).as_dict(),
        },
    )
