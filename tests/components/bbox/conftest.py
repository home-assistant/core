"""Configure tests for Bbox."""

from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

from aiobbox.models import (
    DeviceInfo,
    EthernetInfo,
    Host,
    IP6Address,
    ParentalControl,
    PingInfo,
    PLCInfo,
    Router,
    RouterDisplay,
    RouterUsing,
    RouterVersion,
    ScanInfo,
    WANIPStats,
    WANStats,
    WirelessByBand,
    WirelessInfo,
)
import pytest

from homeassistant.components.bbox.const import CONF_BASE_URL, DOMAIN
from homeassistant.const import CONF_PASSWORD

from .const import (
    DEVICE_1_HOSTNAME,
    DEVICE_1_MAC,
    DEVICE_2_HOSTNAME,
    DEVICE_2_MAC,
    TEST_BASE_URL,
    TEST_FIRMWARE_VERSION,
    TEST_MODEL_NAME,
    TEST_PASSWORD,
    TEST_SERIAL_NUMBER,
)

from tests.common import Generator, MockConfigEntry


@pytest.fixture
def mock_setup_entry() -> Generator[AsyncMock]:
    """Override async_setup_entry."""
    with patch(
        "homeassistant.components.bbox.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        yield mock_setup_entry


@pytest.fixture
def mock_bbox_api() -> Generator[AsyncMock]:
    """Mock a Bbox API client."""
    with (
        patch(
            "homeassistant.components.bbox.config_flow.BboxApi",
            autospec=True,
        ) as mock_api,
        patch(
            "homeassistant.components.bbox.BboxApi",
            new=mock_api,
        ),
    ):
        client = mock_api.return_value
        client.authenticate = AsyncMock(return_value=True)
        client.close = AsyncMock(return_value=True)

        client.get_router_info = AsyncMock(
            return_value=Router(
                now=datetime(2025, 10, 30, 12, 8, 3, tzinfo=UTC),
                status=1,
                numberofboots=10,
                modelname=TEST_MODEL_NAME,
                modelclass="F5696b",
                optimisation=1,
                user_configured=1,
                serialnumber=TEST_SERIAL_NUMBER,
                display=RouterDisplay(luminosity=2, luminosity_extender=100, state="."),
                main=RouterVersion(
                    version=TEST_FIRMWARE_VERSION,
                    date=datetime(2025, 9, 25, 14, 38, 50, tzinfo=UTC),
                ),
                reco=RouterVersion(
                    version=TEST_FIRMWARE_VERSION,
                    date=datetime(2025, 9, 25, 14, 29, 16, tzinfo=UTC),
                ),
                running=RouterVersion(
                    version=TEST_FIRMWARE_VERSION,
                    date=datetime(2025, 9, 25, 14, 38, 16, tzinfo=UTC),
                ),
                spl=RouterVersion(version=""),
                tpl=RouterVersion(version=""),
                ldr1=RouterVersion(version="4.4.20"),
                ldr2=RouterVersion(version="4.4.20"),
                firstusedate=datetime(2025, 7, 23, 6, 30, 42, tzinfo=UTC),
                uptime=630757,
                lastFactoryReset=0,
                using=RouterUsing(ipv4=1, ipv6=1, ftth=1, adsl=0, vdsl=0),
                isCellularEnable=1,
                newihm=1,
                newihmCdc=1,
            )
        )

        client.get_wan_ip_stats = AsyncMock(
            return_value=WANIPStats(
                rx=WANStats(
                    packets=2533896,
                    bytes=2974093659,
                    packetserrors=0,
                    packetsdiscards=0,
                    occupation=54,
                    bandwidth=5432000,
                    maxBandwidth=8000000,
                    contractualBandwidth=8000000,
                ),
                tx=WANStats(
                    packets=1353118,
                    bytes=1105440591,
                    packetserrors=0,
                    packetsdiscards=0,
                    occupation=1,
                    bandwidth=173000,
                    maxBandwidth=1000000,
                    contractualBandwidth=1000000,
                ),
            )
        )

        client.get_hosts = AsyncMock(
            return_value=[
                Host(
                    id=1,
                    active=True,
                    devicetype="computer",
                    duid=None,
                    guest=False,
                    hostname=DEVICE_1_HOSTNAME,
                    ipaddress="192.168.1.10",
                    lease=86400,
                    link="2.4",
                    macaddress=DEVICE_1_MAC,
                    type="DHCP",
                    firstseen=datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC),
                    lastseen=3600,
                    serialNumber=None,
                    ip6address=None,
                    ethernet=EthernetInfo(
                        physicalport=1,
                        logicalport=1,
                        speed=1000,
                        mode="auto",
                    ),
                    wireless=WirelessInfo(
                        wexindex=0,
                        static=False,
                        band="2.4",
                        txUsage=0,
                        rxUsage=0,
                        estimatedRate=144,
                        rssi0=-45,
                        mcs=7,
                        rate=144,
                    ),
                    wirelessByBand=[],
                    plc=PLCInfo(
                        rxphyrate=0,
                        txphyrate=0,
                        associateddevice=0,
                        interface=0,
                        ethernetspeed=0,
                    ),
                    informations=DeviceInfo(  # codespell:ignore informations
                        type="computer",
                        manufacturer="Generic",
                        model="PC",
                        icon="computer",
                        operatingSystem="Windows",
                        version="10",
                    ),
                    parentalcontrol=ParentalControl(
                        enable=False,
                        status="allowed",
                        statusRemaining=0,
                        statusUntil=None,
                    ),
                    ping=PingInfo(average=1),
                    scan=ScanInfo(services=["http", "ssh"]),
                ),
                Host(
                    id=2,
                    active=True,
                    devicetype="phone",
                    duid=None,
                    guest=False,
                    hostname=DEVICE_2_HOSTNAME,
                    ipaddress="192.168.1.11",
                    lease=86400,
                    link="5",
                    macaddress=DEVICE_2_MAC,
                    type="DHCP",
                    firstseen=datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC),
                    lastseen=1800,
                    serialNumber=None,
                    ip6address=[
                        IP6Address(
                            ipaddress="2001:db8::1",
                            status="active",
                            lastseen=datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC),
                            lastscan=datetime(2025, 1, 1, 10, 0, 0, tzinfo=UTC),
                        )
                    ],
                    ethernet=EthernetInfo(
                        physicalport=0,
                        logicalport=0,
                        speed=0,
                        mode="",
                    ),
                    wireless=WirelessInfo(
                        wexindex=0,
                        static=False,
                        band="5",
                        txUsage=0,
                        rxUsage=0,
                        estimatedRate=866,
                        rssi0=-65,
                        mcs=9,
                        rate=866,
                    ),
                    wirelessByBand=[
                        WirelessByBand(
                            band="5",
                            txUsage=0,
                            rxUsage=0,
                            estimatedRate=866,
                            rssi0=-65,
                            mcs=9,
                            rate=866,
                        )
                    ],
                    plc=PLCInfo(
                        rxphyrate=0,
                        txphyrate=0,
                        associateddevice=0,
                        interface=0,
                        ethernetspeed=0,
                    ),
                    informations=DeviceInfo(  # codespell:ignore informations
                        type="phone",
                        manufacturer="Apple",
                        model="iPhone",
                        icon="phone",
                        operatingSystem="iOS",
                        version="17",
                    ),
                    parentalcontrol=ParentalControl(
                        enable=False,
                        status="allowed",
                        statusRemaining=0,
                        statusUntil=None,
                    ),
                    ping=PingInfo(average=2),
                    scan=ScanInfo(services=[]),
                ),
            ]
        )

        yield client


@pytest.fixture
def mock_config_entry() -> MockConfigEntry:
    """Mock a Bbox config entry."""
    return MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_BASE_URL: TEST_BASE_URL,
            CONF_PASSWORD: TEST_PASSWORD,
        },
        unique_id=TEST_SERIAL_NUMBER,
        version=1,
    )


@pytest.fixture
def mock_coordinator() -> Generator[AsyncMock]:
    """Mock a Bbox coordinator."""
    with patch(
        "homeassistant.components.bbox.coordinator.BboxRouter",
        autospec=True,
    ) as mock_coordinator:
        coordinator = mock_coordinator.return_value
        coordinator.async_config_entry_first_refresh = AsyncMock()
        coordinator.async_shutdown = AsyncMock()
        yield coordinator
