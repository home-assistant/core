"""Test the Lutron Caseta config flow."""
import asyncio
from unittest.mock import AsyncMock, patch

from pylutron_caseta.pairing import PAIR_CA, PAIR_CERT, PAIR_KEY
from pylutron_caseta.smartbridge import Smartbridge
import pytest

from homeassistant import config_entries, data_entry_flow, setup
from homeassistant.components.lutron_caseta import DOMAIN
import homeassistant.components.lutron_caseta.config_flow as CasetaConfigFlow
from homeassistant.components.lutron_caseta.const import (
    CONF_CA_CERTS,
    CONF_CERTFILE,
    CONF_KEYFILE,
    ERROR_CANNOT_CONNECT,
    STEP_IMPORT_FAILED,
)
from homeassistant.components.zeroconf import ATTR_HOSTNAME
from homeassistant.const import CONF_HOST

from tests.common import MockConfigEntry

MOCK_ASYNC_PAIR_SUCCESS = {
    PAIR_KEY: "mock_key",
    PAIR_CERT: "mock_cert",
    PAIR_CA: "mock_ca",
}


class MockBridge:
    """Mock Lutron bridge that emulates configured connected status."""

    def __init__(self, can_connect=True):
        """Initialize MockBridge instance with configured mock connectivity."""
        self.can_connect = can_connect
        self.is_currently_connected = False

    async def connect(self):
        """Connect the mock bridge."""
        if self.can_connect:
            self.is_currently_connected = True

    def is_connected(self):
        """Return whether the mock bridge is connected."""
        return self.is_currently_connected

    async def close(self):
        """Close the mock bridge connection."""
        self.is_currently_connected = False


async def test_bridge_import_flow(hass):
    """Test a bridge entry gets created and set up during the import flow."""

    entry_mock_data = {
        CONF_HOST: "1.1.1.1",
        CONF_KEYFILE: "",
        CONF_CERTFILE: "",
        CONF_CA_CERTS: "",
    }

    with patch(
        "homeassistant.components.lutron_caseta.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry, patch(
        "homeassistant.components.lutron_caseta.async_setup", return_value=True
    ), patch.object(
        Smartbridge, "create_tls"
    ) as create_tls:
        create_tls.return_value = MockBridge(can_connect=True)

        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=entry_mock_data,
        )

    assert result["type"] == "create_entry"
    assert result["title"] == CasetaConfigFlow.ENTRY_DEFAULT_TITLE
    assert result["data"] == entry_mock_data
    await hass.async_block_till_done()
    assert len(mock_setup_entry.mock_calls) == 1


async def test_bridge_cannot_connect(hass):
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

    assert result["type"] == "form"
    assert result["step_id"] == STEP_IMPORT_FAILED
    assert result["errors"] == {"base": ERROR_CANNOT_CONNECT}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == CasetaConfigFlow.ABORT_REASON_CANNOT_CONNECT


async def test_bridge_cannot_connect_unknown_error(hass):
    """Test checking for connection and encountering an unknown error."""

    entry_mock_data = {
        CONF_HOST: "",
        CONF_KEYFILE: "",
        CONF_CERTFILE: "",
        CONF_CA_CERTS: "",
    }

    with patch.object(Smartbridge, "create_tls") as create_tls:
        mock_bridge = MockBridge()
        mock_bridge.connect = AsyncMock(side_effect=Exception())
        create_tls.return_value = mock_bridge
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=entry_mock_data,
        )

    assert result["type"] == "form"
    assert result["step_id"] == STEP_IMPORT_FAILED
    assert result["errors"] == {"base": ERROR_CANNOT_CONNECT}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == CasetaConfigFlow.ABORT_REASON_CANNOT_CONNECT


async def test_duplicate_bridge_import(hass):
    """Test that creating a bridge entry with a duplicate host errors."""

    entry_mock_data = {
        CONF_HOST: "1.1.1.1",
        CONF_KEYFILE: "",
        CONF_CERTFILE: "",
        CONF_CA_CERTS: "",
    }
    mock_entry = MockConfigEntry(domain=DOMAIN, data=entry_mock_data)
    mock_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.lutron_caseta.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        # Mock entry added, try initializing flow with duplicate host
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={"source": config_entries.SOURCE_IMPORT},
            data=entry_mock_data,
        )

    assert result["type"] == data_entry_flow.RESULT_TYPE_ABORT
    assert result["reason"] == CasetaConfigFlow.ABORT_REASON_ALREADY_CONFIGURED
    assert len(mock_setup_entry.mock_calls) == 0


async def test_already_configured_with_ignored(hass):
    """Test ignored entries do not break checking for existing entries."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    config_entry = MockConfigEntry(domain=DOMAIN, data={}, source="ignore")
    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={
            CONF_HOST: "1.1.1.1",
            CONF_KEYFILE: "",
            CONF_CERTFILE: "",
            CONF_CA_CERTS: "",
        },
    )
    assert result["type"] == "form"


async def test_form_user(hass, tmpdir):
    """Test we get the form and can pair."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    hass.config.config_dir = await hass.async_add_executor_job(
        tmpdir.mkdir, "tls_assets"
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] is None
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
        },
    )
    await hass.async_block_till_done()
    assert result2["type"] == "form"
    assert result2["step_id"] == "link"

    with patch(
        "homeassistant.components.lutron_caseta.config_flow.async_pair",
        return_value=MOCK_ASYNC_PAIR_SUCCESS,
    ), patch(
        "homeassistant.components.lutron_caseta.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.lutron_caseta.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result3["type"] == "create_entry"
    assert result3["title"] == "1.1.1.1"
    assert result3["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_KEYFILE: "lutron_caseta-1.1.1.1-key.pem",
        CONF_CERTFILE: "lutron_caseta-1.1.1.1-cert.pem",
        CONF_CA_CERTS: "lutron_caseta-1.1.1.1-ca.pem",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1


async def test_form_user_pairing_fails(hass, tmpdir):
    """Test we get the form and we handle pairing failure."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    hass.config.config_dir = await hass.async_add_executor_job(
        tmpdir.mkdir, "tls_assets"
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] is None
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
        },
    )
    await hass.async_block_till_done()
    assert result2["type"] == "form"
    assert result2["step_id"] == "link"

    with patch(
        "homeassistant.components.lutron_caseta.config_flow.async_pair",
        side_effect=asyncio.TimeoutError,
    ), patch(
        "homeassistant.components.lutron_caseta.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.lutron_caseta.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result3["type"] == "form"
    assert result3["errors"] == {"base": "cannot_connect"}
    assert len(mock_setup.mock_calls) == 0
    assert len(mock_setup_entry.mock_calls) == 0


async def test_form_user_reuses_existing_assets_when_pairing_again(hass, tmpdir):
    """Test the tls assets saved on disk are reused when pairing again."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    hass.config.config_dir = await hass.async_add_executor_job(
        tmpdir.mkdir, "tls_assets"
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": config_entries.SOURCE_USER}
    )
    assert result["type"] == "form"
    assert result["errors"] is None
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
        },
    )
    await hass.async_block_till_done()
    assert result2["type"] == "form"
    assert result2["step_id"] == "link"

    with patch(
        "homeassistant.components.lutron_caseta.config_flow.async_pair",
        return_value=MOCK_ASYNC_PAIR_SUCCESS,
    ), patch(
        "homeassistant.components.lutron_caseta.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.lutron_caseta.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result3["type"] == "create_entry"
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
    assert result["type"] == "form"
    assert result["errors"] is None
    assert result["step_id"] == "user"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "1.1.1.1",
        },
    )
    await hass.async_block_till_done()
    assert result2["type"] == "form"
    assert result2["step_id"] == "link"

    with patch.object(Smartbridge, "create_tls") as create_tls, patch(
        "homeassistant.components.lutron_caseta.async_setup", return_value=True
    ), patch(
        "homeassistant.components.lutron_caseta.async_setup_entry",
        return_value=True,
    ):
        create_tls.return_value = MockBridge(can_connect=True)
        result3 = await hass.config_entries.flow.async_configure(
            result2["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result3["type"] == "create_entry"
    assert result3["title"] == "1.1.1.1"
    assert result3["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_KEYFILE: "lutron_caseta-1.1.1.1-key.pem",
        CONF_CERTFILE: "lutron_caseta-1.1.1.1-cert.pem",
        CONF_CA_CERTS: "lutron_caseta-1.1.1.1-ca.pem",
    }


async def test_zeroconf_host_already_configured(hass, tmpdir):
    """Test starting a flow from discovery when the host is already configured."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    hass.config.config_dir = await hass.async_add_executor_job(
        tmpdir.mkdir, "tls_assets"
    )

    config_entry = MockConfigEntry(domain=DOMAIN, data={CONF_HOST: "1.1.1.1"})

    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data={
            CONF_HOST: "1.1.1.1",
            ATTR_HOSTNAME: "lutron-abc.local.",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"


async def test_zeroconf_lutron_id_already_configured(hass):
    """Test starting a flow from discovery when lutron id already configured."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    config_entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: "4.5.6.7"}, unique_id="abc"
    )

    config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data={
            CONF_HOST: "1.1.1.1",
            ATTR_HOSTNAME: "lutron-abc.local.",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == "abort"
    assert result["reason"] == "already_configured"
    assert config_entry.data[CONF_HOST] == "1.1.1.1"


async def test_zeroconf_not_lutron_device(hass):
    """Test starting a flow from discovery when it is not a lutron device."""
    await setup.async_setup_component(hass, "persistent_notification", {})

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data={
            CONF_HOST: "1.1.1.1",
            ATTR_HOSTNAME: "notlutron-abc.local.",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == "abort"
    assert result["reason"] == "not_lutron_device"


@pytest.mark.parametrize(
    "source", (config_entries.SOURCE_ZEROCONF, config_entries.SOURCE_HOMEKIT)
)
async def test_zeroconf(hass, source, tmpdir):
    """Test starting a flow from discovery."""
    await setup.async_setup_component(hass, "persistent_notification", {})
    hass.config.config_dir = await hass.async_add_executor_job(
        tmpdir.mkdir, "tls_assets"
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": source},
        data={
            CONF_HOST: "1.1.1.1",
            ATTR_HOSTNAME: "lutron-abc.local.",
        },
    )
    await hass.async_block_till_done()

    assert result["type"] == "form"
    assert result["step_id"] == "link"

    with patch(
        "homeassistant.components.lutron_caseta.config_flow.async_pair",
        return_value=MOCK_ASYNC_PAIR_SUCCESS,
    ), patch(
        "homeassistant.components.lutron_caseta.async_setup", return_value=True
    ) as mock_setup, patch(
        "homeassistant.components.lutron_caseta.async_setup_entry",
        return_value=True,
    ) as mock_setup_entry:
        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {},
        )
        await hass.async_block_till_done()

    assert result2["type"] == "create_entry"
    assert result2["title"] == "abc"
    assert result2["data"] == {
        CONF_HOST: "1.1.1.1",
        CONF_KEYFILE: "lutron_caseta-abc-key.pem",
        CONF_CERTFILE: "lutron_caseta-abc-cert.pem",
        CONF_CA_CERTS: "lutron_caseta-abc-ca.pem",
    }
    assert len(mock_setup.mock_calls) == 1
    assert len(mock_setup_entry.mock_calls) == 1
