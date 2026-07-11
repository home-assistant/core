"""Tests for UniFi AP Direct config flow."""

from unifi_ap import UniFiAPConnectionException

from homeassistant.components.unifi_direct.const import DOMAIN
from homeassistant.config_entries import SOURCE_IMPORT, SOURCE_USER
from homeassistant.const import (
    CONF_HOST,
    CONF_HOSTS,
    CONF_PASSWORD,
    CONF_PORT,
    CONF_USERNAME,
)
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from .conftest import MOCK_CONFIG

from tests.common import MockConfigEntry


async def test_user_flow_success(
    hass: HomeAssistant, mock_setup_entry, mock_unifiap
) -> None:
    """Test a successful config flow."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOSTS: [
                {
                    CONF_HOST: "192.168.1.2",
                    CONF_USERNAME: "admin",
                    CONF_PASSWORD: "password",
                    CONF_PORT: 22,
                }
            ]
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "UniFi AP (192.168.1.2)"
    assert result["data"] == {
        CONF_HOSTS: [
            {
                CONF_HOST: "192.168.1.2",
                CONF_USERNAME: "admin",
                CONF_PASSWORD: "password",
                CONF_PORT: 22,
            }
        ]
    }


async def test_user_flow_success_with_multiple_hosts(
    hass: HomeAssistant, mock_setup_entry, mock_unifiap
) -> None:
    """Test a successful multi-AP config flow with per-host credentials."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input={
            CONF_HOSTS: [
                {
                    CONF_HOST: "192.168.1.2",
                    CONF_USERNAME: "admin",
                    CONF_PASSWORD: "password",
                    CONF_PORT: 22,
                },
                {
                    CONF_HOST: "192.168.1.3",
                    CONF_USERNAME: "admin2",
                    CONF_PASSWORD: "password2",
                    CONF_PORT: 2222,
                },
            ]
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "UniFi AP (192.168.1.2, 192.168.1.3)"
    assert result["data"] == {
        CONF_HOSTS: [
            {
                CONF_HOST: "192.168.1.2",
                CONF_USERNAME: "admin",
                CONF_PASSWORD: "password",
                CONF_PORT: 22,
            },
            {
                CONF_HOST: "192.168.1.3",
                CONF_USERNAME: "admin2",
                CONF_PASSWORD: "password2",
                CONF_PORT: 2222,
            },
        ]
    }


async def test_user_flow_cannot_connect(
    hass: HomeAssistant, mock_setup_entry, mock_unifiap
) -> None:
    """Test config flow when connection fails."""
    # Make the UniFiAP.get_clients raise an exception
    mock_unifiap.return_value.get_clients.side_effect = UniFiAPConnectionException(
        "fail"
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    user_input = {
        CONF_HOSTS: [
            {
                CONF_HOST: "192.168.1.2",
                CONF_USERNAME: "admin",
                CONF_PASSWORD: "password",
                CONF_PORT: 22,
            }
        ]
    }
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "cannot_connect"}
    assert result["description_placeholders"] == {"host": "192.168.1.2"}

    # Remove the UniFiAP.get_clients side effect and see if the flow recovers
    mock_unifiap.return_value.get_clients.side_effect = None

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input=user_input
    )
    assert result["type"] is FlowResultType.CREATE_ENTRY


async def test_user_flow_entry_exists(
    hass: HomeAssistant, mock_setup_entry, mock_unifiap, mock_config_entry
) -> None:
    """Test where an entry already exists and we try to set it up."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": SOURCE_USER}
    )
    assert result["type"] is FlowResultType.FORM

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        user_input=MOCK_CONFIG,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_migrate_single_host_entry_to_multi_host_config(
    hass: HomeAssistant, mock_setup_entry, mock_unifiap
) -> None:
    """Test a legacy single-host entry is migrated to the multi-host structure."""
    config_entry = MockConfigEntry(
        domain=DOMAIN,
        title="UniFi AP (192.168.1.2)",
        data={
            CONF_HOST: "192.168.1.2",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
            CONF_PORT: 22,
        },
        version=1,
        minor_version=1,
    )
    config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.version == 2
    assert config_entry.minor_version == 1
    assert config_entry.data == {
        CONF_HOSTS: [
            {
                CONF_HOST: "192.168.1.2",
                CONF_USERNAME: "admin",
                CONF_PASSWORD: "password",
                CONF_PORT: 22,
            }
        ]
    }


async def test_import_flow(hass: HomeAssistant, mock_setup_entry, mock_unifiap) -> None:
    """Test import initiated flow from legacy YAML configuration."""
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_HOST: "192.168.1.2",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
            CONF_PORT: 22,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "UniFi AP (192.168.1.2)"
    assert result["data"] == {
        CONF_HOSTS: [
            {
                CONF_HOST: "192.168.1.2",
                CONF_USERNAME: "admin",
                CONF_PASSWORD: "password",
                CONF_PORT: 22,
            }
        ]
    }


async def test_import_flow_entry_exists(
    hass: HomeAssistant, mock_setup_entry, mock_unifiap, mock_config_entry
) -> None:
    """Test import flow aborts when entry already exists."""
    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_HOST: "192.168.1.2",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
            CONF_PORT: 22,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_import_flow_cannot_connect(
    hass: HomeAssistant, mock_setup_entry, mock_unifiap
) -> None:
    """Test import config flow when connection fails."""
    mock_unifiap.return_value.get_clients.side_effect = UniFiAPConnectionException(
        "fail"
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": SOURCE_IMPORT},
        data={
            CONF_HOST: "192.168.1.2",
            CONF_USERNAME: "admin",
            CONF_PASSWORD: "password",
            CONF_PORT: 22,
        },
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
