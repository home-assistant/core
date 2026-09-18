"""Test the Lutron Caseta config flow."""

from ipaddress import ip_address
from pathlib import Path
import ssl
from unittest.mock import AsyncMock, patch

from pylutron_caseta.pairing import PAIR_CA, PAIR_CERT, PAIR_KEY
from pylutron_caseta.smartbridge import Smartbridge
import pytest

from homeassistant import config_entries
from homeassistant.components.lutron_caseta import (
    DOMAIN,
    config_flow as CasetaConfigFlow,
)
from homeassistant.components.lutron_caseta.const import (
    CONF_CA_CERTS,
    CONF_CERTFILE,
    CONF_KEYFILE,
    ERROR_CANNOT_CONNECT,
    STEP_IMPORT_FAILED,
)
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from . import ENTRY_MOCK_DATA, MockBridge

from tests.common import MockConfigEntry

ATTR_HOSTNAME = "hostname"

EMPTY_MOCK_CONFIG_ENTRY = {
    CONF_HOST: "",
    CONF_KEYFILE: "",
    CONF_CERTFILE: "",
    CONF_CA_CERTS: "",
}


MOCK_ASYNC_PAIR_SUCCESS = {
    PAIR_KEY: "mock_key",
    PAIR_CERT: "mock_cert",
    PAIR_CA: "mock_ca",
}


async def test_bridge_import_flow(hass: HomeAssistant) -> None:
    """Test a bridge entry gets created and set up during the import flow."""

    entry_mock_data = {
        CONF_HOST: "1.1.1.1",
        CONF_KEYFILE: "",
        CONF_CERTFILE: "",
        CONF_CA_CERTS: "",
    }

    with (
        patch(
            "homeassistant.components.lutron_caseta.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
        patch("homeassistant.components.lutron_caseta.async_setup", return_value=True),
        patch.object(
            Smartbridge,
            "create_tls",
        ) as create_tls,
    ):
        create_tls.return_value = MockBridge(can_connect=True)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=entry_mock_data,
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == CasetaConfigFlow.ENTRY_DEFAULT_TITLE
    assert result["data"] == entry_mock_data
    assert result["result"].unique_id == "000004d2"

    assert len(mock_setup_entry.mock_calls) == 1


async def test_bridge_cannot_connect(hass: HomeAssistant) -> None:
    """Test checking for connection and cannot_connect error."""

    entry_mock_data = {
        CONF_HOST: "not.a.valid.host",
        CONF_KEYFILE: "",
        CONF_CERTFILE: "",
        CONF_CA_CERTS: "",
    }

    with patch.object(Smartbridge, "create_tls") as create_tls:
        create_tls.return_value = MockBridge(can_connect=False)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=entry_mock_data,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == STEP_IMPORT_FAILED
    assert result["errors"] == {"base": ERROR_CANNOT_CONNECT}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == CasetaConfigFlow.ABORT_REASON_CANNOT_CONNECT


async def test_bridge_cannot_connect_unknown_error(hass: HomeAssistant) -> None:
    """Test checking for connection and encountering an unknown error."""

    with patch.object(Smartbridge, "create_tls") as create_tls:
        mock_bridge = MockBridge()
        mock_bridge.connect = AsyncMock(side_effect=TimeoutError)
        create_tls.return_value = mock_bridge
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=EMPTY_MOCK_CONFIG_ENTRY,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == STEP_IMPORT_FAILED
    assert result["errors"] == {"base": ERROR_CANNOT_CONNECT}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == CasetaConfigFlow.ABORT_REASON_CANNOT_CONNECT


async def test_bridge_invalid_ssl_error(hass: HomeAssistant) -> None:
    """Test checking for connection and encountering invalid ssl certs."""

    with patch.object(Smartbridge, "create_tls", side_effect=ssl.SSLError):
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=EMPTY_MOCK_CONFIG_ENTRY,
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == STEP_IMPORT_FAILED
    assert result["errors"] == {"base": ERROR_CANNOT_CONNECT}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == CasetaConfigFlow.ABORT_REASON_CANNOT_CONNECT


async def test_duplicate_bridge_import(hass: HomeAssistant) -> None:
    """Test that creating a bridge entry with a duplicate host errors."""

    mock_entry = MockConfigEntry(domain=DOMAIN, data=ENTRY_MOCK_DATA)
    mock_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.lutron_caseta.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        # Mock entry added, try initializing flow with duplicate host
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=ENTRY_MOCK_DATA,
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert len(mock_setup_entry.mock_calls) == 0


async def test_already_configured_with_ignored(hass: HomeAssistant) -> None:
    """Test ignored entries do not break checking for existing entries."""

    config_entry = MockConfigEntry(
        domain=DOMAIN, data={}, source=config_entries.SOURCE_IGNORE
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={CONF_HOST: "1.1.1.1"},
    )
    assert result["type"] is FlowResultType.FORM


async def test_form_user(hass: HomeAssistant, tmp_path: Path) -> None:
    """Test we get the form and can pair."""
    config_dir = tmp_path / "tls_assets"
    await hass.async_add_executor_job(config_dir.mkdir)
    hass.config.config_dir = str(config_dir)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
        },
    )
    await hass.async_block_till_done()
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "link"

    with (
        patch(
            "homeassistant.components.lutron_caseta.config_flow.async_pair",
            return_value=MOCK_ASYNC_PAIR_SUCCESS,
        ),
        patch(
            "homeassistant.components.lutron_caseta.async_setup", return_value=True
        ) as mock_setup,
        patch(
            "homeassistant.components.lutron_caseta.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "1.1.1.1"
    assert result3["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_KEYFILE: "lutron_caseta-1.1.1.1-key.pem",
        CONF_CERTFILE: "lutron_caseta-1.1.1.1-cert.pem",
        CONF_CA_CERTS: "lutron_caseta-1.1.1.1-ca.pem",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_user_pairing_fails(hass: HomeAssistant, tmp_path: Path) -> None:
    """Test we get the form and we handle pairing failure."""
    config_dir = tmp_path / "tls_assets"
    await hass.async_add_executor_job(config_dir.mkdir)
    hass.config.config_dir = str(config_dir)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
        },
    )
    await hass.async_block_till_done()
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "link"

    with (
        patch(
            "homeassistant.components.lutron_caseta.config_flow.async_pair",
            side_effect=TimeoutError,
        ),
        patch(
            "homeassistant.components.lutron_caseta.async_setup", return_value=True
        ) as mock_setup,
        patch(
            "homeassistant.components.lutron_caseta.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"] == {"base": "cannot_connect"}
    assert len(mock_setup.mock_calls) == 0
    assert len(mock_setup_entry.mock_calls) == 0


async def test_form_user_reuses_existing_assets_when_pairing_again(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    """Test the tls assets saved on disk are reused when pairing again."""
    config_dir = tmp_path / "tls_assets"
    await hass.async_add_executor_job(config_dir.mkdir)
    hass.config.config_dir = str(config_dir)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
        },
    )
    await hass.async_block_till_done()
    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "link"

    with (
        patch(
            "homeassistant.components.lutron_caseta.config_flow.async_pair",
            return_value=MOCK_ASYNC_PAIR_SUCCESS,
        ),
        patch(
            "homeassistant.components.lutron_caseta.async_setup", return_value=True
        ) as mock_setup,
        patch(
            "homeassistant.components.lutron_caseta.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "1.1.1.1"
    assert result3["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_KEYFILE: "lutron_caseta-1.1.1.1-key.pem",
        CONF_CERTFILE: "lutron_caseta-1.1.1.1-cert.pem",
        CONF_CA_CERTS: "lutron_caseta-1.1.1.1-ca.pem",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1

    with patch(
        "homeassistant.components.lutron_caseta.async_unload_entry", return_value=True
    ) as mock_unload:
        await hass.config_entries.async_remove(result3["result"].entry_id)
        await hass.async_block_till_done()

    assert len(mock_unload.mock_calls) == 1

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] is None
    assert result["step_id"] == "user"

    with patch.object(Smartbridge, "create_tls") as create_tls:
        create_tls.return_value = MockBridge(can_connect=True)
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                CONF_HOST: "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "link"

    with (
        patch("homeassistant.components.lutron_caseta.async_setup", return_value=True),
        patch(
            "homeassistant.components.lutron_caseta.async_setup_entry",
            return_value=True,
        ),
    ):
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "1.1.1.1"
    assert result3["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_KEYFILE: "lutron_caseta-1.1.1.1-key.pem",
        CONF_CERTFILE: "lutron_caseta-1.1.1.1-cert.pem",
        CONF_CA_CERTS: "lutron_caseta-1.1.1.1-ca.pem",
    }


async def test_zeroconf_host_already_configured(
    hass: HomeAssistant, tmp_path: Path
) -> None:
    """Test starting a flow from discovery when the host is already configured."""
    config_dir = tmp_path / "tls_assets"
    await hass.async_add_executor_job(config_dir.mkdir)
    hass.config.config_dir = str(config_dir)

    config_entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "1.1.1.1"})

    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("1.1.1.1"),
            ip_addresses=[ip_address("1.1.1.1")],
            hostname="LuTrOn-abc.local.",
            name="mock_name",
            port=None,
            properties={},
            type="mock_type",
        ),
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_lutron_id_already_configured(hass: HomeAssistant) -> None:
    """Test starting a flow from discovery when lutron id already configured."""

    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "4.5.6.7"}, unique_id="abc"
    )

    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("1.1.1.1"),
            ip_addresses=[ip_address("1.1.1.1")],
            hostname="LuTrOn-abc.local.",
            name="mock_name",
            port=None,
            properties={},
            type="mock_type",
        ),
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert config_entry.data[CONF_HOST] == "1.1.1.1"


async def test_zeroconf_not_lutron_device(hass: HomeAssistant) -> None:
    """Test starting a flow from discovery when it is not a lutron device."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("1.1.1.1"),
            ip_addresses=[ip_address("1.1.1.1")],
            hostname="notlutron-abc.local.",
            name="mock_name",
            port=None,
            properties={},
            type="mock_type",
        ),
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_lutron_device"


@pytest.mark.parametrize(
    "source", [config_entries.SOURCE_ZEROCONF, config_entries.SOURCE_HOMEKIT]
)
async def test_zeroconf(hass: HomeAssistant, source, tmp_path: Path) -> None:
    """Test starting a flow from discovery."""
    config_dir = tmp_path / "tls_assets"
    await hass.async_add_executor_job(config_dir.mkdir)
    hass.config.config_dir = str(config_dir)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": source},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("1.1.1.1"),
            ip_addresses=[ip_address("1.1.1.1")],
            hostname="LuTrOn-abc.local.",
            name="mock_name",
            port=None,
            properties={},
            type="mock_type",
        ),
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "link"

    with (
        patch(
            "homeassistant.components.lutron_caseta.config_flow.async_pair",
            return_value=MOCK_ASYNC_PAIR_SUCCESS,
        ),
        patch(
            "homeassistant.components.lutron_caseta.async_setup", return_value=True
        ) as mock_setup,
        patch(
            "homeassistant.components.lutron_caseta.async_setup_entry",
            return_value=True,
        ) as mock_setup_entry,
    ):
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "abc"
    assert result2["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_KEYFILE: "lutron_caseta-abc-key.pem",
        CONF_CERTFILE: "lutron_caseta-abc-cert.pem",
        CONF_CA_CERTS: "lutron_caseta-abc-ca.pem",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_zeroconf_discovery_athena(hass: HomeAssistant) -> None:
    """Test Athena processors are discovered over zeroconf.

    This does not exercise the `athena*` manifest zeroconf matcher itself:
    matching on that property is done by
    homeassistant/components/zeroconf/discovery.py before this integration's
    flow is ever reached, and is verified by hassfest and by the committed
    homeassistant/generated/zeroconf.py, not by this test. What this test
    pins down is that a real Athena hostname is parsed into the unique_id
    that matches the processor's actual serial number, so that a discovered
    entry and a manually-added one converge on the same config entry instead
    of duplicating.
    """
    # 093cbfd8 is serial_to_unique_id(154976216), the real serial reported
    # by this Athena processor. If async_step_zeroconf's
    # `hostname.split("-")[1].replace(".local.", "")` derivation ever breaks
    # (e.g. stops stripping the trailing dot, or splits on the wrong
    # separator), the discovered unique_id would no longer equal "093cbfd8"
    # and this existing entry would not be found, so the flow would proceed
    # to the "link" step instead of aborting with "already_configured".
    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "4.5.6.7"}, unique_id="093cbfd8"
    )
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("10.81.4.11"),
            ip_addresses=[ip_address("10.81.4.11")],
            hostname="Lutron-093cbfd8.local.",
            name="Lutron Status (2)._lutron._tcp.local.",
            port=22,
            properties={
                "SYSTYPE": "AthenaProcessor",
                "SERNUM": "093CBFD8",
                "DEVCLASS": "08130101",
                "CODEVER": "26.06.45f000",
            },
            type="_lutron._tcp.local.",
        ),
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert config_entry.data[CONF_HOST] == "10.81.4.11"
