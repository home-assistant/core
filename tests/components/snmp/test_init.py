"""SNMP tests."""

from unittest.mock import Mock, patch

from pysnmp.hlapi.v3arch.asyncio import SnmpEngine
from pysnmp.hlapi.v3arch.asyncio.cmdgen import LCD

from homeassistant.components import snmp
from homeassistant.components.snmp.const import DOMAIN
from homeassistant.const import CONF_HOST, CONF_PORT, EVENT_HOMEASSISTANT_STOP
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry


async def test_async_get_snmp_engine(hass: HomeAssistant) -> None:
    """Test async_get_snmp_engine."""
    engine = await snmp.async_get_snmp_engine(hass)
    assert isinstance(engine, SnmpEngine)
    engine2 = await snmp.async_get_snmp_engine(hass)
    assert engine is engine2
    with patch.object(LCD, "unconfigure") as mock_unconfigure:
        hass.bus.async_fire(EVENT_HOMEASSISTANT_STOP)
        await hass.async_block_till_done()
    assert mock_unconfigure.called


async def test_async_setup_entry_custom_port(hass: HomeAssistant) -> None:
    """Test async_setup_entry with a custom port."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            CONF_HOST: "1.2.3.4",
            CONF_PORT: 1161,
            "baseoid": "1.3.6.1.2.1.1",
            "version": "2c",
        },
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.snmp.UdpTransportTarget.create",
            return_value=Mock(),
        ) as mock_create,
        patch(
            "homeassistant.components.snmp.SnmpUpdateCoordinator.async_config_entry_first_refresh",
        ),
        patch(
            "homeassistant.components.snmp.coordinator.get_cmd",
            return_value=(None, None, None, []),
        ),
    ):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    # Verify that UdpTransportTarget.create was called with the custom port
    mock_create.assert_called_once()
    args, _ = mock_create.call_args
    assert args[0] == ("1.2.3.4", 1161)
