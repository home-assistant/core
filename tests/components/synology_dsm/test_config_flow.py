"""Tests for the Synology DSM config flow."""

from ipaddress import ip_address
from unittest.mock import AsyncMock, MagicMock, Mock, patch

import pytest
from synology_dsm.api.file_station.models import SynoFileSharedFolder
from synology_dsm.exceptions import (
    SynologyDSMException,
    SynologyDSMLogin2SAFailedException,
    SynologyDSMLogin2SARequiredException,
    SynologyDSMLoginInvalidException,
    SynologyDSMRequestException,
)
from syrupy import SnapshotAssertion

from homeassistant.components.synology_dsm.config_flow import CONF_OTP_CODE
from homeassistant.components.synology_dsm.const import (
    CONF_BACKUP_PATH,
    CONF_BACKUP_SHARE,
    CONF_SNAPSHOT_QUALITY,
    DOMAIN,
)
from homeassistant.config_entries import SOURCE_SSDP, SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import (
    CONF_HOST,
    CONF_MAC,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.ssdp import (
    ATTR_UPNP_FRIENDLY_NAME,
    ATTR_UPNP_SERIAL,
    SsdpServiceInfo,
)
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .common import mock_dsm_information
from .consts import (
    DEVICE_TOKEN,
    HOST,
    MACS,
    PASSWORD,
    PORT,
    SERIAL,
    SERIAL_2,
    USE_SSL,
    USERNAME,
    VERIFY_SSL,
)

from tests.common import MockConfigEntry


@pytest.fixture(name="service")
def mock_controller_service():
    """Mock a successful service."""
    with patch("homeassistant.components.synology_dsm.config_flow.SynologyDSM") as dsm:
        dsm.login = AsyncMock(return_value=True)
        dsm.update = AsyncMock(return_value=True)

        dsm.surveillance_station.update = AsyncMock(return_value=True)
        dsm.upgrade.update = AsyncMock(return_value=True)
        dsm.utilisation = Mock(cpu_user_load=1, update=AsyncMock(return_value=True))
        dsm.network = Mock(update=AsyncMock(return_value=True), macs=MACS)
        dsm.storage = Mock(
            disks_ids=["sda", "sdb", "sdc"],
            volumes_ids=["volume_1"],
            update=AsyncMock(return_value=True),
        )
        dsm.information = mock_dsm_information()
        dsm.file = AsyncMock(get_shared_folders=AsyncMock(return_value=None))
        yield dsm


@pytest.fixture(name="service_2sa")
def mock_controller_service_2sa():
    """Mock a successful service with 2SA login."""
    with patch("homeassistant.components.synology_dsm.config_flow.SynologyDSM") as dsm:
        dsm.login = AsyncMock(
            side_effect=SynologyDSMLogin2SARequiredException(USERNAME)
        )
        dsm.update = AsyncMock(return_value=True)

        dsm.surveillance_station.update = AsyncMock(return_value=True)
        dsm.upgrade.update = AsyncMock(return_value=True)
        dsm.utilisation = Mock(cpu_user_load=1, update=AsyncMock(return_value=True))
        dsm.network = Mock(update=AsyncMock(return_value=True), macs=MACS)
        dsm.storage = Mock(
            disks_ids=["sda", "sdb", "sdc"],
            volumes_ids=["volume_1"],
            update=AsyncMock(return_value=True),
        )
        dsm.information = mock_dsm_information()
        dsm.file = AsyncMock(get_shared_folders=AsyncMock(return_value=None))
        yield dsm


@pytest.fixture(name="service_vdsm")
def mock_controller_service_vdsm():
    """Mock a successful service."""
    with patch("homeassistant.components.synology_dsm.config_flow.SynologyDSM") as dsm:
        dsm.login = AsyncMock(return_value=True)
        dsm.update = AsyncMock(return_value=True)

        dsm.surveillance_station.update = AsyncMock(return_value=True)
        dsm.upgrade.update = AsyncMock(return_value=True)
        dsm.utilisation = Mock(cpu_user_load=1, update=AsyncMock(return_value=True))
        dsm.network = Mock(update=AsyncMock(return_value=True), macs=MACS)
        dsm.storage = Mock(
            disks_ids=[],
            volumes_ids=["volume_1"],
            update=AsyncMock(return_value=True),
        )
        dsm.information = mock_dsm_information()
        dsm.file = AsyncMock(get_shared_folders=AsyncMock(return_value=None))
        yield dsm


@pytest.fixture(name="service_with_filestation")
def mock_controller_service_with_filestation():
    """Mock a successful service with filestation support."""
    with patch("homeassistant.components.synology_dsm.config_flow.SynologyDSM") as dsm:
        dsm.login = AsyncMock(return_value=True)
        dsm.update = AsyncMock(return_value=True)

        dsm.surveillance_station.update = AsyncMock(return_value=True)
        dsm.upgrade.update = AsyncMock(return_value=True)
        dsm.utilisation = Mock(cpu_user_load=1, update=AsyncMock(return_value=True))
        dsm.network = Mock(update=AsyncMock(return_value=True), macs=MACS)
        dsm.storage = Mock(
            disks_ids=["sda", "sdb", "sdc"],
            volumes_ids=["volume_1"],
            update=AsyncMock(return_value=True),
        )
        dsm.information = mock_dsm_information()
        dsm.file = AsyncMock(
            get_shared_folders=AsyncMock(
                return_value=[
                    SynoFileSharedFolder(
                        additional=None,
                        is_dir=True,
                        name="HA Backup",
                        path="/ha_backup",
                    )
                ]
            )
        )

        yield dsm


@pytest.fixture(name="service_failed")
def mock_controller_service_failed():
    """Mock a failed service."""
    with patch("homeassistant.components.synology_dsm.config_flow.SynologyDSM") as dsm:
        dsm.login = AsyncMock(return_value=True)
        dsm.update = AsyncMock(return_value=True)

        dsm.surveillance_station.update = AsyncMock(return_value=True)
        dsm.upgrade.update = AsyncMock(return_value=True)
        dsm.utilisation = Mock(cpu_user_load=None, update=AsyncMock(return_value=True))
        dsm.network = Mock(update=AsyncMock(return_value=True), macs=[])
        dsm.storage = Mock(
            disks_ids=[],
            volumes_ids=[],
            update=AsyncMock(return_value=True),
        )
        dsm.information = mock_dsm_information(serial=None)
        dsm.file = AsyncMock(get_shared_folders=AsyncMock(return_value=None))
        yield dsm


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user(
    hass: HomeAssistant,
    service: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test user config."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}, data=None
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.synology_dsm.config_flow.SynologyDSM",
        return_value=service,
    ):
        # test with all provided
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={
                CONF_HOST: HOST,
                CONF_PORT: PORT,
                CONF_SSL: USE_SSL,
                CONF_VERIFY_SSL: VERIFY_SSL,
                CONF_USERNAME: USERNAME,
                CONF_PASSWORD: PASSWORD,
            },
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == SERIAL
    assert result["title"] == HOST
    assert result["data"] == snapshot

    service.information.serial = SERIAL_2
    with patch(
        "homeassistant.components.synology_dsm.config_flow.SynologyDSM",
        return_value=service,
    ):
        # test without port + False SSL
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={
                CONF_HOST: HOST,
                CONF_SSL: False,
                CONF_VERIFY_SSL: VERIFY_SSL,
                CONF_USERNAME: USERNAME,
                CONF_PASSWORD: PASSWORD,
            },
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == SERIAL_2
    assert result["title"] == HOST
    assert result["data"] == snapshot


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_2sa(
    hass: HomeAssistant, service_2sa: MagicMock, snapshot: SnapshotAssertion
) -> None:
    """Test user with 2sa authentication config."""
    with patch(
        "homeassistant.components.synology_dsm.config_flow.SynologyDSM",
        return_value=service_2sa,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_HOST: HOST, CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "2sa"

    # Failed the first time because was too slow to enter the code
    service_2sa.return_value.login = Mock(
        side_effect=SynologyDSMLogin2SAFailedException
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_OTP_CODE: "000000"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "2sa"
    assert result["errors"] == {CONF_OTP_CODE: "otp_failed"}

    # Successful login with 2SA code
    service_2sa.login = AsyncMock(return_value=True)
    service_2sa.device_token = DEVICE_TOKEN

    with patch(
        "homeassistant.components.synology_dsm.config_flow.SynologyDSM",
        return_value=service_2sa,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_OTP_CODE: "123456"}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == SERIAL
    assert result["title"] == HOST
    assert result["data"] == snapshot


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_vdsm(
    hass: HomeAssistant, service_vdsm: MagicMock, snapshot: SnapshotAssertion
) -> None:
    """Test user config."""
    with patch(
        "homeassistant.components.synology_dsm.config_flow.SynologyDSM",
        return_value=service_vdsm,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=None
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.synology_dsm.config_flow.SynologyDSM",
        return_value=service_vdsm,
    ):
        # test with all provided
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={
                CONF_HOST: HOST,
                CONF_PORT: PORT,
                CONF_SSL: USE_SSL,
                CONF_VERIFY_SSL: VERIFY_SSL,
                CONF_USERNAME: USERNAME,
                CONF_PASSWORD: PASSWORD,
            },
        )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == SERIAL
    assert result["title"] == HOST
    assert result["data"] == snapshot


@pytest.mark.usefixtures("mock_setup_entry")
async def test_user_with_filestation(
    hass: HomeAssistant,
    service_with_filestation: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test user config."""
    with patch(
        "homeassistant.components.synology_dsm.config_flow.SynologyDSM",
        return_value=service_with_filestation,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": SOURCE_USER}, data=None
        )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    with patch(
        "homeassistant.components.synology_dsm.config_flow.SynologyDSM",
        return_value=service_with_filestation,
    ):
        # test with all provided
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={
                CONF_HOST: HOST,
                CONF_PORT: PORT,
                CONF_SSL: USE_SSL,
                CONF_VERIFY_SSL: VERIFY_SSL,
                CONF_USERNAME: USERNAME,
                CONF_PASSWORD: PASSWORD,
            },
        )

        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "backup_share"

        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {CONF_BACKUP_SHARE: "/ha_backup", CONF_BACKUP_PATH: "automatic_ha_backups"},
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == SERIAL
    assert result["title"] == HOST
    assert result["data"] == snapshot


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reauth(hass: HomeAssistant, service: MagicMock) -> None:
    """Test reauthentication."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: HOST,
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: f"{PASSWORD}_invalid",
        },
        unique_id=SERIAL,
    )
    entry.add_to_hass(hass)

    result = await entry.start_reauth_flow(hass)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    with patch(
        "homeassistant.components.synology_dsm.config_flow.SynologyDSM",
        return_value=service,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_USERNAME: USERNAME,
                CONF_PASSWORD: PASSWORD,
            },
        )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfig_user(hass: HomeAssistant, service: MagicMock) -> None:
    """Test re-configuration of already existing entry by user."""
    MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "wrong_host",
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
        },
        unique_id=SERIAL,
    ).add_to_hass(hass)

    with (
        patch(
            "homeassistant.config_entries.ConfigEntries.async_reload",
            return_value=True,
        ),
        patch(
            "homeassistant.components.synology_dsm.config_flow.SynologyDSM",
            return_value=service,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_HOST: HOST, CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        )
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "reconfigure_successful"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_login_failed(hass: HomeAssistant, service: MagicMock) -> None:
    """Test when we have errors during login."""
    service.return_value.login = Mock(
        side_effect=(SynologyDSMLoginInvalidException(USERNAME))
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: HOST, CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_USERNAME: "invalid_auth"}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_connection_failed(hass: HomeAssistant, service: MagicMock) -> None:
    """Test when we have errors during connection."""
    service.return_value.login = Mock(
        side_effect=SynologyDSMRequestException(OSError("arg"))
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: HOST, CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {CONF_HOST: "cannot_connect"}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_unknown_failed(hass: HomeAssistant, service: MagicMock) -> None:
    """Test when we have an unknown error."""
    service.return_value.login = Mock(side_effect=SynologyDSMException(None, None))

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: HOST, CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "unknown"}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_missing_data_after_login(
    hass: HomeAssistant, service_failed: MagicMock
) -> None:
    """Test when we have errors during connection."""
    with patch(
        "homeassistant.components.synology_dsm.config_flow.SynologyDSM",
        return_value=service_failed,
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": SOURCE_USER},
            data={CONF_HOST: HOST, CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD},
        )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "missing_data"}


@pytest.mark.usefixtures("mock_setup_entry")
async def test_form_ssdp(
    hass: HomeAssistant, service: MagicMock, snapshot: SnapshotAssertion
) -> None:
    """Test we can setup from ssdp."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            ssdp_location="http://192.168.1.5:5000",
            upnp={
                ATTR_UPNP_FRIENDLY_NAME: "mydsm",
                ATTR_UPNP_SERIAL: "001132XXXX99",  # MAC address, but SSDP does not have `-`
            },
        ),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "link"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.synology_dsm.config_flow.SynologyDSM",
        return_value=service,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == SERIAL
    assert result["title"] == "mydsm"
    assert result["data"] == snapshot


@pytest.mark.usefixtures("mock_setup_entry")
async def test_reconfig_ssdp(hass: HomeAssistant, service: MagicMock) -> None:
    """Test re-configuration of already existing entry by ssdp."""

    MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.3",
            CONF_VERIFY_SSL: VERIFY_SSL,
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
            CONF_MAC: MACS,
        },
        unique_id=SERIAL,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            ssdp_location="http://192.168.1.5:5000",
            upnp={
                ATTR_UPNP_FRIENDLY_NAME: "mydsm",
                ATTR_UPNP_SERIAL: "001132XXXX59",  # Existing in MACS[0], but SSDP does not have `-`
            },
        ),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"


@pytest.mark.usefixtures("mock_setup_entry")
@pytest.mark.parametrize(
    ("current_host", "new_host"),
    [
        ("some.fqdn", "192.168.1.5"),
        ("192.168.1.5", "abcd:1234::"),
        ("abcd:1234::", "192.168.1.5"),
    ],
)
async def test_skip_reconfig_ssdp(
    hass: HomeAssistant, current_host: str, new_host: str, service: MagicMock
) -> None:
    """Test re-configuration of already existing entry by ssdp."""

    MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: current_host,
            CONF_VERIFY_SSL: VERIFY_SSL,
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
            CONF_MAC: MACS,
        },
        unique_id=SERIAL,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            ssdp_location=f"http://{new_host}:5000",
            upnp={
                ATTR_UPNP_FRIENDLY_NAME: "mydsm",
                ATTR_UPNP_SERIAL: "001132XXXX59",  # Existing in MACS[0], but SSDP does not have `-`
            },
        ),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_existing_ssdp(hass: HomeAssistant, service: MagicMock) -> None:
    """Test abort of already existing entry by ssdp."""

    MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "192.168.1.5",
            CONF_VERIFY_SSL: VERIFY_SSL,
            CONF_USERNAME: USERNAME,
            CONF_PASSWORD: PASSWORD,
            CONF_MAC: MACS,
        },
        unique_id=SERIAL,
    ).add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_SSDP},
        data=SsdpServiceInfo(
            ssdp_usn="mock_usn",
            ssdp_st="mock_st",
            ssdp_location="http://192.168.1.5:5000",
            upnp={
                ATTR_UPNP_FRIENDLY_NAME: "mydsm",
                ATTR_UPNP_SERIAL: "001132XXXX59",  # Existing in MACS[0], but SSDP does not have `-`
            },
        ),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow(
    hass: HomeAssistant, service_with_filestation: MagicMock
) -> None:
    """Test config flow options."""
    with (
        patch(
            "homeassistant.components.synology_dsm.common.SynologyDSM",
            return_value=service_with_filestation,
        ),
        patch("homeassistant.components.synology_dsm.PLATFORMS", return_value=[]),
    ):
        config_entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_HOST: HOST,
                CONF_PORT: PORT,
                CONF_SSL: USE_SSL,
                CONF_USERNAME: USERNAME,
                CONF_PASSWORD: PASSWORD,
                CONF_MAC: MACS[0],
            },
            unique_id=SERIAL,
        )
        config_entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert config_entry.options == {CONF_BACKUP_SHARE: None, CONF_BACKUP_PATH: None}

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_init(config_entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        user_input={
            CONF_SNAPSHOT_QUALITY: 0,
            CONF_BACKUP_PATH: "my_nackup_path",
            CONF_BACKUP_SHARE: "/ha_backup",
        },
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert config_entry.options[CONF_SNAPSHOT_QUALITY] == 0
    assert config_entry.options[CONF_BACKUP_PATH] == "my_nackup_path"
    assert config_entry.options[CONF_BACKUP_SHARE] == "/ha_backup"


@pytest.mark.usefixtures("mock_setup_entry")
async def test_discovered_via_zeroconf(
    hass: HomeAssistant, service: MagicMock, snapshot: SnapshotAssertion
) -> None:
    """Test we can setup from zeroconf."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("192.168.1.5"),
            ip_addresses=[ip_address("192.168.1.5")],
            port=5000,
            hostname="mydsm.local.",
            type="_http._tcp.local.",
            name="mydsm._http._tcp.local.",
            properties={
                "mac_address": "00:11:32:XX:XX:99|00:11:22:33:44:55",  # MAC address, but SSDP does not have `-`
            },
        ),
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "link"
    assert result["errors"] == {}

    with patch(
        "homeassistant.components.synology_dsm.config_flow.SynologyDSM",
        return_value=service,
    ):
        result = await hass.config_entries.flow.async_configure(
            result["flow_id"], {CONF_USERNAME: USERNAME, CONF_PASSWORD: PASSWORD}
        )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["result"].unique_id == SERIAL
    assert result["title"] == "mydsm"
    assert result["data"] == snapshot


@pytest.mark.usefixtures("mock_setup_entry")
async def test_discovered_via_zeroconf_missing_mac(
    hass: HomeAssistant, service: MagicMock
) -> None:
    """Test we abort if the mac address is missing."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("192.168.1.5"),
            ip_addresses=[ip_address("192.168.1.5")],
            port=5000,
            hostname="mydsm.local.",
            type="_http._tcp.local.",
            name="mydsm._http._tcp.local.",
            properties={},
        ),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_mac_address"
