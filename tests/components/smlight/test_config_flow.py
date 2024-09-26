"""Test the SMLIGHT SLZB config flow."""

from ipaddress import ip_address
from unittest.mock import AsyncMock, MagicMock

from pysmlight.exceptions import SmlightAuthError, SmlightConnectionError
import pytest

from homeassistant.components import zeroconf
from homeassistant.components.smlight.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_HOST, MOCK_PASSWORD, MOCK_USERNAME

from tests.common import MockConfigEntry

DISCOVERY_INFO = zeroconf.ZeroconfServiceInfo(
    ip_address=ip_address("127.0.0.1"),
    ip_addresses=[ip_address("127.0.0.1")],
    hostname="slzb-06.local.",
    name="mock_name",
    port=6638,
    properties={"mac": "AA:BB:CC:DD:EE:FF"},
    type="mock_type",
)

DISCOVERY_INFO_LEGACY = zeroconf.ZeroconfServiceInfo(
    ip_address=ip_address("127.0.0.1"),
    ip_addresses=[ip_address("127.0.0.1")],
    hostname="slzb-06.local.",
    name="mock_name",
    port=6638,
    properties={},
    type="mock_type",
)


@pytest.mark.usefixtures("mock_smlight_client")
async def test_user_flow(hass: HomeAssistant, mock_setup_entry: AsyncMock) -> None:
    """Test the full manual user flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: MOCK_HOST,
        },
    )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "SLZB-06p7"
    assert result2["data"] == {
        CONF_HOST: MOCK_HOST,
    }
    assert result2["context"]["unique_id"] == "aa:bb:cc:dd:ee:ff"
    assert len(mock_setup_entry.mock_calls) == 1


async def test_zeroconf_flow(
    hass: HomeAssistant,
    mock_smlight_client: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the zeroconf flow."""

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=DISCOVERY_INFO
    )

    assert result["description_placeholders"] == {"host": MOCK_HOST}
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm_discovery"

    progress = hass.config_entries.flow.async_progress()
    assert len(progress) == 1
    assert progress[0]["flow_id"] == result["flow_id"]
    assert progress[0]["context"]["confirm_only"] is True

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["context"]["source"] == "zeroconf"
    assert result2["context"]["unique_id"] == "aa:bb:cc:dd:ee:ff"
    assert result2["title"] == "slzb-06"
    assert result2["data"] == {
        CONF_HOST: MOCK_HOST,
    }

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_smlight_client.get_info.mock_calls) == 1


async def test_zeroconf_flow_auth(
    hass: HomeAssistant,
    mock_smlight_client: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the full zeroconf flow including authentication."""
    mock_smlight_client.check_auth_needed.return_value = True

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_ZEROCONF}, data=DISCOVERY_INFO
    )

    assert result["description_placeholders"] == {"host": MOCK_HOST}
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm_discovery"

    progress = hass.config_entries.flow.async_progress()
    assert len(progress) == 1
    assert progress[0]["flow_id"] == result["flow_id"]
    assert progress[0]["context"]["confirm_only"] is True

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "auth"

    progress2 = hass.config_entries.flow.async_progress()
    assert len(progress2) == 1
    assert progress2[0]["flow_id"] == result["flow_id"]

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_USERNAME: MOCK_USERNAME,
            CONF_PASSWORD: MOCK_PASSWORD,
        },
    )

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["context"]["source"] == "zeroconf"
    assert result3["context"]["unique_id"] == "aa:bb:cc:dd:ee:ff"
    assert result3["title"] == "slzb-06"
    assert result3["data"] == {
        CONF_USERNAME: MOCK_USERNAME,
        CONF_PASSWORD: MOCK_PASSWORD,
        CONF_HOST: MOCK_HOST,
    }

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_smlight_client.get_info.mock_calls) == 1


@pytest.mark.usefixtures("mock_smlight_client")
async def test_user_device_exists_abort(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test we abort user flow if device already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_HOST: MOCK_HOST,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_smlight_client")
async def test_zeroconf_device_exists_abort(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test we abort zeroconf flow if device already configured."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=DISCOVERY_INFO,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_invalid_auth(
    hass: HomeAssistant, mock_smlight_client: MagicMock, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle invalid auth."""
    mock_smlight_client.check_auth_needed.return_value = True
    mock_smlight_client.authenticate.side_effect = SmlightAuthError

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={
            CONF_HOST: MOCK_HOST,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test",
            CONF_PASSWORD: "bad",
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["errors"] == {"base": "invalid_auth"}
    assert result2["step_id"] == "auth"

    mock_smlight_client.authenticate.side_effect = None

    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: "test",
            CONF_PASSWORD: "good",
        },
    )

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["title"] == "SLZB-06p7"
    assert result3["data"] == {
        CONF_HOST: MOCK_HOST,
        CONF_USERNAME: "test",
        CONF_PASSWORD: "good",
    }

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_smlight_client.get_info.mock_calls) == 1


async def test_user_cannot_connect(
    hass: HomeAssistant, mock_smlight_client: MagicMock, mock_setup_entry: AsyncMock
) -> None:
    """Test we handle user cannot connect error."""
    mock_smlight_client.check_auth_needed.side_effect = SmlightConnectionError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: "unknown.local",
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert result["step_id"] == "user"

    mock_smlight_client.check_auth_needed.side_effect = None

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: MOCK_HOST,
        },
    )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["title"] == "SLZB-06p7"

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_smlight_client.get_info.mock_calls) == 1


async def test_auth_cannot_connect(
    hass: HomeAssistant, mock_smlight_client: MagicMock
) -> None:
    """Test we abort auth step on cannot connect error."""
    mock_smlight_client.check_auth_needed.return_value = True

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_HOST: MOCK_HOST,
        },
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"

    mock_smlight_client.check_auth_needed.side_effect = SmlightConnectionError

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: MOCK_USERNAME,
            CONF_PASSWORD: MOCK_PASSWORD,
        },
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "cannot_connect"


async def test_zeroconf_cannot_connect(
    hass: HomeAssistant, mock_smlight_client: MagicMock
) -> None:
    """Test we abort flow on zeroconf cannot connect error."""
    mock_smlight_client.check_auth_needed.side_effect = SmlightConnectionError

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=DISCOVERY_INFO,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm_discovery"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {},
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "cannot_connect"


async def test_zeroconf_legacy_cannot_connect(
    hass: HomeAssistant, mock_smlight_client: MagicMock
) -> None:
    """Test we abort flow on zeroconf discovery unsupported firmware."""
    mock_smlight_client.get_info.side_effect = SmlightConnectionError

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=DISCOVERY_INFO_LEGACY,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.usefixtures("mock_smlight_client")
async def test_zeroconf_legacy_mac(
    hass: HomeAssistant, mock_smlight_client: MagicMock, mock_setup_entry: AsyncMock
) -> None:
    """Test we can get unique id MAC address for older firmwares."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=DISCOVERY_INFO_LEGACY,
    )

    assert result["description_placeholders"] == {"host": MOCK_HOST}

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result2["type"] is FlowResultType.CREATE_ENTRY
    assert result2["context"]["source"] == "zeroconf"
    assert result2["context"]["unique_id"] == "aa:bb:cc:dd:ee:ff"
    assert result2["title"] == "slzb-06"
    assert result2["data"] == {
        CONF_HOST: MOCK_HOST,
    }

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_smlight_client.get_info.mock_calls) == 2


async def test_reauth_flow(
    hass: HomeAssistant,
    mock_smlight_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reauth flow completes successfully."""
    mock_smlight_client.check_auth_needed.return_value = True
    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: MOCK_USERNAME,
            CONF_PASSWORD: MOCK_PASSWORD,
        },
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "reauth_successful"
    assert mock_config_entry.data == {
        CONF_USERNAME: MOCK_USERNAME,
        CONF_PASSWORD: MOCK_PASSWORD,
        CONF_HOST: MOCK_HOST,
    }

    assert len(mock_smlight_client.authenticate.mock_calls) == 1
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_reauth_auth_error(
    hass: HomeAssistant,
    mock_smlight_client: MagicMock,
    mock_config_entry: MockConfigEntry,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test reauth flow with authentication error."""
    mock_smlight_client.check_auth_needed.return_value = True
    mock_smlight_client.authenticate.side_effect = SmlightAuthError

    mock_config_entry.add_to_hass(hass)
    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: MOCK_USERNAME,
            CONF_PASSWORD: "test-bad",
        },
    )

    assert result2["type"] is FlowResultType.FORM
    assert result2["step_id"] == "reauth_confirm"

    mock_smlight_client.authenticate.side_effect = None
    result3 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: MOCK_USERNAME,
            CONF_PASSWORD: MOCK_PASSWORD,
        },
    )

    assert result3["type"] is FlowResultType.ABORT
    assert result3["reason"] == "reauth_successful"

    assert mock_config_entry.data == {
        CONF_USERNAME: MOCK_USERNAME,
        CONF_PASSWORD: MOCK_PASSWORD,
        CONF_HOST: MOCK_HOST,
    }

    assert len(mock_smlight_client.authenticate.mock_calls) == 2
    assert len(hass.config_entries.async_entries(DOMAIN)) == 1


async def test_reauth_connect_error(
    hass: HomeAssistant,
    mock_smlight_client: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reauth flow with error."""
    mock_smlight_client.check_auth_needed.return_value = True
    mock_smlight_client.authenticate.side_effect = SmlightConnectionError

    mock_config_entry.add_to_hass(hass)

    result = await mock_config_entry.start_reauth_flow(hass)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result2 = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {
            CONF_USERNAME: MOCK_USERNAME,
            CONF_PASSWORD: MOCK_PASSWORD,
        },
    )

    assert result2["type"] is FlowResultType.ABORT
    assert result2["reason"] == "cannot_connect"
    assert len(mock_smlight_client.authenticate.mock_calls) == 1
