"""Tests for the Elgato Key Light config flow."""

from ipaddress import ip_address
from unittest.mock import AsyncMock, MagicMock

from elgato import ElgatoConnectionError
import pytest

from homeassistant.components.elgato.const import DOMAIN
from homeassistant.config_entries import SOURCE_USER, SOURCE_ZEROCONF
from homeassistant.const import CONF_HOST, CONF_MAC, CONF_SOURCE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from tests.common import MockConfigEntry


async def test_full_user_flow_implementation(
    hass: HomeAssistant,
    mock_elgato: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the full manual user flow from start to finish."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={CONF_HOST: "127.0.0.1"}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY

    config_entry = result["result"]
    assert config_entry.unique_id == "CN11A1A00001"
    assert config_entry.data == {
        CONF_HOST: "127.0.0.1",
        CONF_MAC: None,
    }
    assert not config_entry.options

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_elgato.info.mock_calls) == 1


async def test_full_zeroconf_flow_implementation(
    hass: HomeAssistant,
    mock_elgato: MagicMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test the zeroconf flow from start to finish."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("127.0.0.1"),
            ip_addresses=[ip_address("127.0.0.1")],
            hostname="example.local.",
            name="mock_name",
            port=9123,
            properties={"id": "AA:BB:CC:DD:EE:FF"},
            type="mock_type",
        ),
    )

    assert result["description_placeholders"] == {"serial_number": "CN11A1A00001"}
    assert result["step_id"] == "zeroconf_confirm"
    assert result["type"] is FlowResultType.FORM

    progress = hass.config_entries.flow.async_progress()
    assert len(progress) == 1
    assert progress[0].get("flow_id") == result["flow_id"]
    assert "context" in progress[0]
    assert progress[0]["context"].get("confirm_only") is True

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input={}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY

    config_entry = result["result"]
    assert config_entry.unique_id == "CN11A1A00001"
    assert config_entry.data == {
        CONF_HOST: "127.0.0.1",
        CONF_MAC: "AA:BB:CC:DD:EE:FF",
    }
    assert not config_entry.options

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_elgato.info.mock_calls) == 1


async def test_connection_error(
    hass: HomeAssistant,
    mock_elgato: MagicMock,
) -> None:
    """Test we show user form on Elgato Key Light connection error."""
    mock_elgato.info.side_effect = ElgatoConnectionError
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: "127.0.0.1"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert result["step_id"] == "user"

    # Recover from error
    mock_elgato.info.side_effect = None

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: "127.0.0.2"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY

    config_entry = result["result"]
    assert config_entry.unique_id == "CN11A1A00001"
    assert config_entry.data == {
        CONF_HOST: "127.0.0.2",
        CONF_MAC: None,
    }
    assert not config_entry.options


async def test_zeroconf_connection_error(
    hass: HomeAssistant,
    mock_elgato: MagicMock,
) -> None:
    """Test we abort zeroconf flow on Elgato Key Light connection error."""
    mock_elgato.info.side_effect = ElgatoConnectionError
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("127.0.0.1"),
            ip_addresses=[ip_address("127.0.0.1")],
            hostname="mock_hostname",
            name="mock_name",
            port=9123,
            properties={},
            type="mock_type",
        ),
    )

    assert result["reason"] == "cannot_connect"
    assert result["type"] is FlowResultType.ABORT


@pytest.mark.usefixtures("mock_elgato")
async def test_user_device_exists_abort(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test we abort zeroconf flow if Elgato Key Light device already configured."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_USER},
        data={CONF_HOST: "127.0.0.1"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


@pytest.mark.usefixtures("mock_elgato")
async def test_zeroconf_device_exists_abort(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test we abort zeroconf flow if Elgato Key Light device already configured."""
    mock_config_entry.add_to_hass(hass)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("127.0.0.1"),
            ip_addresses=[ip_address("127.0.0.1")],
            hostname="mock_hostname",
            name="mock_name",
            port=9123,
            properties={},
            type="mock_type",
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries[0].data[CONF_HOST] == "127.0.0.1"

    # Check the host updates on discovery
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={CONF_SOURCE: SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("127.0.0.2"),
            ip_addresses=[ip_address("127.0.0.2")],
            hostname="mock_hostname",
            name="mock_name",
            port=9123,
            properties={},
            type="mock_type",
        ),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"

    entries = hass.config_entries.async_entries(DOMAIN)
    assert entries[0].data[CONF_HOST] == "127.0.0.2"


async def test_zeroconf_during_onboarding(
    hass: HomeAssistant,
    mock_elgato: MagicMock,
    mock_setup_entry: AsyncMock,
    mock_onboarding: MagicMock,
) -> None:
    """Test the zeroconf creates an entry during onboarding."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_ZEROCONF},
        data=ZeroconfServiceInfo(
            ip_address=ip_address("127.0.0.1"),
            ip_addresses=[ip_address("127.0.0.1")],
            hostname="example.local.",
            name="mock_name",
            port=9123,
            properties={"id": "AA:BB:CC:DD:EE:FF"},
            type="mock_type",
        ),
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY

    config_entry = result["result"]
    assert config_entry.unique_id == "CN11A1A00001"
    assert config_entry.data == {
        CONF_HOST: "127.0.0.1",
        CONF_MAC: "AA:BB:CC:DD:EE:FF",
    }
    assert not config_entry.options

    assert len(mock_setup_entry.mock_calls) == 1
    assert len(mock_elgato.info.mock_calls) == 1
    assert len(mock_onboarding.mock_calls) == 1
