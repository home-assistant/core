"""Tests for the modbus config flow."""

from syrupy.assertion import SnapshotAssertion

from homeassistant.components.modbus.const import MODBUS_DOMAIN, TCP
from homeassistant.config_entries import SOURCE_IMPORT
from homeassistant.const import CONF_HOST, CONF_NAME, CONF_PORT, CONF_TYPE
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

_HUB_CONFIG = {
    CONF_TYPE: TCP,
    CONF_NAME: "tcp_config",
    CONF_HOST: "1.2.3.4",
    CONF_PORT: 502,
}
_HUB_CONFIG_GENERAL = {
    CONF_TYPE: TCP,
    CONF_NAME: "tcp_config2",
    CONF_HOST: "1.2.3.4",
    CONF_PORT: 503,
}
_HUB_CONFIG_PROPERTIES = {
    CONF_TYPE: TCP,
    CONF_NAME: "tcp_config2",
    CONF_HOST: "1.2.3.4",
    CONF_PORT: 502,
}
_HUB_CONFIG_NAME = {
    CONF_TYPE: TCP,
    CONF_NAME: "tcp_config",
    CONF_HOST: "1.2.3.4",
    CONF_PORT: 503,
}


async def test_import_flow(
    hass: HomeAssistant,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the import configuration flow."""
    for hub_config in (_HUB_CONFIG, _HUB_CONFIG_GENERAL):
        result = await hass.config_entries.flow.async_init(
            MODBUS_DOMAIN,
            context={"source": SOURCE_IMPORT},
            data=hub_config,
        )
        assert result.get("type") is FlowResultType.CREATE_ENTRY
    assert hass.config_entries.async_entries(MODBUS_DOMAIN) == snapshot


async def test_import_flow_update_match_properties(hass: HomeAssistant) -> None:
    """Test the import configuration flow.

    Existing entry matches on type/host/port.
    """
    result = await hass.config_entries.flow.async_init(
        MODBUS_DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=_HUB_CONFIG,
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    entries = hass.config_entries.async_entries(MODBUS_DOMAIN)
    assert len(entries) == 1
    assert entries[0].data == _HUB_CONFIG

    # Change host/port, should update existing entry
    result = await hass.config_entries.flow.async_init(
        MODBUS_DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=_HUB_CONFIG_PROPERTIES,
    )
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"
    entries = hass.config_entries.async_entries(MODBUS_DOMAIN)
    assert len(entries) == 1
    assert entries[0].data == _HUB_CONFIG_PROPERTIES


async def test_import_flow_update_match_name(hass: HomeAssistant) -> None:
    """Test the import configuration flow.

    Existing entry matches on yaml name.
    """
    result = await hass.config_entries.flow.async_init(
        MODBUS_DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=_HUB_CONFIG,
    )
    assert result.get("type") is FlowResultType.CREATE_ENTRY
    original_entries = hass.config_entries.async_entries(MODBUS_DOMAIN)
    assert len(original_entries) == 1
    assert original_entries[0].data == _HUB_CONFIG

    # Update settings, including type and IP but keep old name
    result = await hass.config_entries.flow.async_init(
        MODBUS_DOMAIN,
        context={"source": SOURCE_IMPORT},
        data=_HUB_CONFIG_NAME,
    )
    assert result.get("type") is FlowResultType.ABORT
    assert result.get("reason") == "already_configured"
