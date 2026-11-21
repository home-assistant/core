"""Common fixtures for the NEPViewer tests."""

from collections.abc import Generator
from unittest.mock import AsyncMock, MagicMock, patch

from aionepviewer.models.auth import AuthData
from aionepviewer.models.device import Device, DeviceStatisticsOverview
from aionepviewer.models.module import SiteModulesData
from aionepviewer.models.site import Site, SiteDetail, SiteOverview
import pytest

from homeassistant.components.nepviewer.const import DOMAIN
from homeassistant.const import CONF_EMAIL, CONF_PASSWORD

from tests.common import MockConfigEntry


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Return a mock config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_EMAIL: "test@example.com",
            CONF_PASSWORD: "test_password",
        },
        unique_id="test_uid",
    )


@pytest.fixture
def mock_nepviewer() -> Generator[MagicMock]:
    """Return a mock NepViewer client patched in __init__."""

    mock_auth_data = AuthData(
        {
            "userInfo": {"uid": "test_uid", "email": "test@example.com"},
            "tokenInfo": {"token": "test_token", "expiresAt": 9999999999},
            "siteCount": 1,
        }
    )
    mock_site = Site({"sid": "test_sid", "siteName": "Test Site"})
    mock_device = Device({"sid": "test_sid", "sn": "TEST_SN", "alias": "Test Device"})
    mock_site_overview = SiteOverview(
        {
            "statisticsProduction": {"today": "5.0", "total": "100.0"},
            "energy": {"PVPanel": {"power": 1500.0}},
        }
    )
    mock_device_overview = DeviceStatisticsOverview(
        {
            "totalNow": 1500.0,
            "production": {"today": "5.0", "total": "100.0"},
        }
    )
    mock_site_modules = SiteModulesData(
        {
            "list": [
                {
                    "sn": "TEST_SN",
                    "modules": [
                        {
                            "plcSN": "TEST_SN_1",
                            "addr": 1,
                            "now": 750.0,
                            "todayPower": 2.5,
                            "totalPower": 50.0,
                        },
                    ],
                }
            ],
            "total_plc": 1,
            "is_all": True,
        }
    )
    mock_site_detail = SiteDetail(
        {
            "sid": "test_sid",
            "companyName": "NEP",
            "pvRemark": "Test Panel Brand",
            "model": "Test Panel Model",
        }
    )

    with patch(
        "homeassistant.components.nepviewer.NepViewer", autospec=True
    ) as mock_cls:
        mock_client = mock_cls.return_value
        mock_client.authenticate = AsyncMock(return_value=mock_auth_data)
        mock_client.get_sites = AsyncMock(return_value=[mock_site])
        mock_client.get_devices = AsyncMock(return_value=[mock_device])
        mock_client.get_site_overview = AsyncMock(return_value=mock_site_overview)
        mock_client.get_device_statistics_overview = AsyncMock(
            return_value=mock_device_overview
        )
        mock_client.get_site_modules = AsyncMock(return_value=mock_site_modules)
        mock_client.get_site_detail = AsyncMock(return_value=mock_site_detail)
        yield mock_client


@pytest.fixture
def mock_nepviewer_config_flow() -> Generator[MagicMock]:
    """Return a mock NepViewer client patched in config_flow."""

    mock_auth_data = AuthData(
        {
            "userInfo": {"uid": "test_uid", "email": "test@example.com"},
            "tokenInfo": {"token": "test_token", "expiresAt": 9999999999},
            "siteCount": 1,
        }
    )

    with patch(
        "homeassistant.components.nepviewer.config_flow.NepViewer", autospec=True
    ) as mock_cls:
        mock_client = mock_cls.return_value
        mock_client.authenticate = AsyncMock(return_value=mock_auth_data)
        yield mock_client
