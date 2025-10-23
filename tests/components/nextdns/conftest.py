"""Common fixtures for the NextDNS tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, Mock, patch

from nextdns import (
    AnalyticsDnssec,
    AnalyticsEncryption,
    AnalyticsIpVersions,
    AnalyticsProtocols,
    AnalyticsStatus,
    ConnectionStatus,
    ProfileInfo,
    Settings,
)
import pytest

from homeassistant.components.nextdns.const import CONF_PROFILE_ID, DOMAIN
from homeassistant.const import CONF_API_KEY

from tests.common import (
    MockConfigEntry,
    load_json_array_fixture,
    load_json_object_fixture,
)

ANALYTICS = load_json_object_fixture("analytics.json", DOMAIN)
ANALYTICS_DNSSEC = AnalyticsDnssec(**ANALYTICS["dnssec"])
ANALYTICS_ENCRYPTION = AnalyticsEncryption(**ANALYTICS["encryption"])
ANALYTICS_IP_VERSIONS = AnalyticsIpVersions(**ANALYTICS["ip_versions"])
ANALYTICS_PROTOCOLS = AnalyticsProtocols(**ANALYTICS["protocols"])
ANALYTICS_STATUS = AnalyticsStatus(**ANALYTICS["status"])
CONNECTION_STATUS = ConnectionStatus(
    **load_json_object_fixture("connection_status.json", DOMAIN)
)
PROFILES = load_json_array_fixture("profiles.json", DOMAIN)
SETTINGS = Settings(**load_json_object_fixture("settings.json", DOMAIN))


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.nextdns.async_setup_entry", return_value=True
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return the default mocked config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        title="Fake Profile",
        unique_id="xyz12",
        data={CONF_API_KEY: "fake_api_key", CONF_PROFILE_ID: "xyz12"},
        entry_id="d9aa37407ddac7b964a99e86312288d6",
    )


@pytest.fixture
def mock_nextdns_client() -> Generator[AsyncMock]:
    """Mock a NextDNS client."""

    with (
        patch("homeassistant.components.nextdns.NextDns", autospec=True) as mock_client,
        patch(
            "homeassistant.components.nextdns.config_flow.NextDns",
            new=mock_client,
        ),
    ):
        client = mock_client.create.return_value
        client.clear_logs.return_value = True
        client.connection_status.return_value = CONNECTION_STATUS
        client.get_analytics_dnssec.return_value = ANALYTICS_DNSSEC
        client.get_analytics_encryption.return_value = ANALYTICS_ENCRYPTION
        client.get_analytics_ip_versions.return_value = ANALYTICS_IP_VERSIONS
        client.get_analytics_protocols.return_value = ANALYTICS_PROTOCOLS
        client.get_analytics_status.return_value = ANALYTICS_STATUS
        client.get_profile_id = Mock(return_value="xyz12")
        client.get_profile_name = Mock(return_value="Fake Profile")
        client.get_profiles.return_value = PROFILES
        client.get_settings.return_value = SETTINGS
        client.set_setting.return_value = True
        client.profiles = [ProfileInfo(**PROFILES[0])]
        # Add the create method to the client so tests can set side_effect
        client.create = mock_client.create

        yield client
