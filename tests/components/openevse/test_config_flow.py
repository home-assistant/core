"""Tests for the OpenEVSE sensor platform."""

from ipaddress import ip_address
from unittest.mock import AsyncMock, MagicMock

from openevsehttp.exceptions import AuthenticationError, MissingSerial

from homeassistant.components.openevse.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry


async def test_user_flow(
    hass: HomeAssistant,
    mock_charger: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test user flow create entry with bad charger."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "10.0.0.131"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "OpenEVSE 10.0.0.131"
    assert result["data"] == {CONF_HOST: "10.0.0.131"}
    assert result["result"].unique_id == "deadbeeffeed"


async def test_user_flow_flaky(
    hass: HomeAssistant,
    mock_charger: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test user flow create entry with flaky charger."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    mock_charger.test_and_get.side_effect = TimeoutError
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "10.0.0.131"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    assert result["errors"] == {"base": "cannot_connect"}

    mock_charger.test_and_get.side_effect = None
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "10.0.0.131"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "OpenEVSE 10.0.0.131"
    assert result["data"] == {CONF_HOST: "10.0.0.131"}
    assert result["result"].unique_id == "deadbeeffeed"


async def test_user_flow_duplicate(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_charger: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test user flow aborts when config entry already exists."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "192.168.1.100"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_no_serial(
    hass: HomeAssistant,
    mock_charger: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test user flow handles missing serial gracefully."""
    mock_charger.test_and_get.side_effect = [{}, MissingSerial]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "10.0.0.131"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "OpenEVSE 10.0.0.131"
    assert result["result"].unique_id is None


async def test_import_flow_no_serial(
    hass: HomeAssistant,
    mock_charger: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test import flow handles missing serial gracefully."""
    mock_charger.test_and_get.side_effect = [{}, MissingSerial]

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data={CONF_HOST: "10.0.0.131"}
    )

    # Assert the flow continued to create the entry
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "OpenEVSE 10.0.0.131"
    assert result["result"].unique_id is None


async def test_user_flow_with_auth(
    hass: HomeAssistant,
    mock_charger: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test user flow create entry with authentication."""
    mock_charger.test_and_get.side_effect = [
        AuthenticationError,
        {"serial": "deadbeeffeed"},
    ]
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "10.0.0.131"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "fakeuser", CONF_PASSWORD: "muchpassword"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "OpenEVSE 10.0.0.131"
    assert result["data"] == {
        CONF_HOST: "10.0.0.131",
        CONF_USERNAME: "fakeuser",
        CONF_PASSWORD: "muchpassword",
    }
    assert result["result"].unique_id == "deadbeeffeed"


async def test_user_flow_with_auth_error(
    hass: HomeAssistant, mock_charger: MagicMock
) -> None:
    """Test user flow create entry with authentication error."""
    mock_charger.test_and_get.side_effect = [
        AuthenticationError,
        AuthenticationError,
        {},
    ]
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_HOST: "10.0.0.131"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "fakeuser", CONF_PASSWORD: "muchpassword"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"]["base"] == "invalid_auth"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "fakeuser", CONF_PASSWORD: "muchpassword"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_with_missing_serial(
    hass: HomeAssistant, mock_charger: MagicMock
) -> None:
    """Test user flow create entry with authentication error."""
    mock_charger.test_and_get.side_effect = [AuthenticationError, MissingSerial]
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], {CONF_HOST: "10.0.0.131"}
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "fakeuser", CONF_PASSWORD: "muchpassword"},
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "OpenEVSE 10.0.0.131"
    assert result["data"] == {
        CONF_HOST: "10.0.0.131",
        CONF_USERNAME: "fakeuser",
        CONF_PASSWORD: "muchpassword",
    }
    assert result["result"].unique_id is None


async def test_import_flow(
    hass: HomeAssistant,
    mock_charger: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test import flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data={CONF_HOST: "10.0.0.131"}
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "OpenEVSE 10.0.0.131"
    assert result["data"] == {CONF_HOST: "10.0.0.131"}
    assert result["result"].unique_id == "deadbeeffeed"


async def test_import_flow_bad(
    hass: HomeAssistant,
    mock_charger: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test import flow with bad charger."""
    mock_charger.test_and_get.side_effect = TimeoutError

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_IMPORT}, data={CONF_HOST: "10.0.0.131"}
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unavailable_host"


async def test_import_flow_duplicate(
    hass: HomeAssistant,
    mock_config_entry: MagicMock,
    mock_charger: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test import flow aborts when config entry already exists."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={CONF_HOST: "192.168.1.100"},
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_discovery(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_charger: MagicMock
) -> None:
    """Test zeroconf discovery."""
    discovery_info = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.1.123"),
        ip_addresses=[ip_address("192.168.1.123")],
        hostname="openevse-deadbeeffeed.local.",
        name="openevse-deadbeeffeed._openevse._tcp.local.",
        port=80,
        properties={"id": "deadbeeffeed", "type": "openevse"},
        type="_openevse._tcp.local.",
    )

    # Trigger the zeroconf step
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )

    # Should present a confirmation form
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "discovery_confirm"
    assert result["description_placeholders"] == {
        "name": "OpenEVSE openevse-deadbeeffeed"
    }

    # Confirm the discovery
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    # Should create the entry
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "OpenEVSE openevse-deadbeeffeed"
    assert result["data"] == {CONF_HOST: "192.168.1.123"}
    assert result["result"].unique_id == "deadbeeffeed"


async def test_zeroconf_already_configured_unique_id(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
    mock_charger: MagicMock,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test zeroconf discovery updates info if unique_id is already configured."""
    mock_config_entry.add_to_hass(hass)

    discovery_info = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.1.124"),
        ip_addresses=[ip_address("192.168.1.124"), ip_address("2001:db8::1")],
        hostname="openevse-deadbeeffeed.local.",
        name="openevse-deadbeeffeed._openevse._tcp.local.",
        port=80,
        properties={"id": "deadbeeffeed", "type": "openevse"},
        type="_openevse._tcp.local.",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )

    # Should abort because unique_id matches, but it updates the config entry
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    # Verify the entry IP was updated to the new discovery IP
    assert mock_config_entry.data["host"] == "192.168.1.124"


async def test_zeroconf_connection_error(
    hass: HomeAssistant, mock_charger: MagicMock
) -> None:
    """Test zeroconf discovery with connection failure."""
    mock_charger.test_and_get.side_effect = TimeoutError
    discovery_info = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.1.123"),
        ip_addresses=[ip_address("192.168.1.123"), ip_address("2001:db8::1")],
        hostname="openevse-deadbeeffeed.local.",
        name="openevse-deadbeeffeed._openevse._tcp.local.",
        port=80,
        properties={"id": "deadbeeffeed", "type": "openevse"},
        type="_openevse._tcp.local.",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unavailable_host"


async def test_zeroconf_auth(hass: HomeAssistant, mock_charger: MagicMock) -> None:
    """Test zeroconf discovery with connection failure."""
    mock_charger.test_and_get.side_effect = [AuthenticationError, {}]
    discovery_info = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.1.123"),
        ip_addresses=[ip_address("192.168.1.123"), ip_address("2001:db8::1")],
        hostname="openevse-deadbeeffeed.local.",
        name="openevse-deadbeeffeed._openevse._tcp.local.",
        port=80,
        properties={"id": "deadbeeffeed", "type": "openevse"},
        type="_openevse._tcp.local.",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "fakeuser", CONF_PASSWORD: "muchpassword"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: "192.168.1.123",
        CONF_USERNAME: "fakeuser",
        CONF_PASSWORD: "muchpassword",
    }


async def test_zeroconf_auth_failure(
    hass: HomeAssistant, mock_charger: MagicMock
) -> None:
    """Test zeroconf discovery with connection failure."""
    mock_charger.test_and_get.side_effect = [
        AuthenticationError,
        AuthenticationError,
        {},
    ]
    discovery_info = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.1.123"),
        ip_addresses=[ip_address("192.168.1.123"), ip_address("2001:db8::1")],
        hostname="openevse-deadbeeffeed.local.",
        name="openevse-deadbeeffeed._openevse._tcp.local.",
        port=80,
        properties={"id": "deadbeeffeed", "type": "openevse"},
        type="_openevse._tcp.local.",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert not result["errors"]

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "fakeuser", CONF_PASSWORD: "muchpassword"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "auth"
    assert result["errors"] == {"base": "invalid_auth"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_USERNAME: "fakeuser", CONF_PASSWORD: "muchpassword"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"] == {
        CONF_HOST: "192.168.1.123",
        CONF_USERNAME: "fakeuser",
        CONF_PASSWORD: "muchpassword",
    }


async def test_zeroconf_already_configured_host(
    hass: HomeAssistant, mock_setup_entry: AsyncMock, mock_config_entry: MockConfigEntry
) -> None:
    """Test zeroconf discovery aborts if host is already configured."""
    mock_config_entry.add_to_hass(hass)

    discovery_info = ZeroconfServiceInfo(
        ip_address=ip_address("192.168.1.100"),
        ip_addresses=[ip_address("192.168.1.100"), ip_address("2001:db8::1")],
        hostname="openevse-deadbeeffeed.local.",
        name="openevse-deadbeeffeed._openevse._tcp.local.",
        port=80,
        properties={"id": "deadbeeffeed", "type": "openevse"},
        type="_openevse._tcp.local.",
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=discovery_info,
    )

    # Should abort because the host matches an existing entry
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
