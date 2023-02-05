"""Test the Sungrow Solar Energy sensor."""
from unittest.mock import AsyncMock, Mock, PropertyMock, patch

from aiohttp import ClientConnectorError
from pymodbus.exceptions import ModbusException
from pysungrow import SungrowClient
from pysungrow.definitions.devices.hybrid import sh10rt
from pysungrow.definitions.variables import variables
from pysungrow.definitions.variables.device import OutputType
from pysungrow.identify import SungrowIdentificationResult
import pytest

from homeassistant.components.sungrow.const import DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from ...common import MockConfigEntry
from ...test_util.aiohttp import AiohttpClientMocker

demo_data = dict(
    **{
        v.key: None
        for v in variables
        if sh10rt in v.devices
        and v.key
        not in ("daily_output_energy", "arm_software_version", "dsp_software_version")
    },
    daily_output_energy=42.42,
    arm_software_version="1.1.1",
    dsp_software_version="2.2.2",
)


@pytest.fixture
def config_entry(hass: HomeAssistant, aioclient_mock: AiohttpClientMocker):
    """Add config entry in Home Assistant."""
    aioclient_mock.get("http://1.1.1.1")

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "1.1.1.1",
            "port": 502,
        },
    )
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.sungrow.identify",
            return_value=SungrowIdentificationResult(
                "A1234567890", sh10rt, OutputType.THREE_PHASE_3P4L, []
            ),
        ),
        patch.object(SungrowClient, "refresh", AsyncMock()),
        patch.object(SungrowClient, "data", PropertyMock(return_value=demo_data)),
    ):
        yield entry


async def test_setup(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Test creation and unload with different address variants."""

    await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()
    assert config_entry.state == ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(config_entry.entry_id)
    await hass.async_block_till_done()

    assert config_entry.state is ConfigEntryState.NOT_LOADED
    assert not hass.data.get(DOMAIN)


async def test_device_info(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Test device info."""

    await hass.config_entries.async_setup(config_entry.entry_id)
    device_registry = dr.async_get(hass)
    await hass.async_block_till_done()
    device = device_registry.async_get_device({(DOMAIN, "A1234567890")})
    await hass.async_block_till_done()

    assert device is not None
    assert device.configuration_url == "http://1.1.1.1"
    assert device.entry_type is None
    assert device.identifiers == {(DOMAIN, "A1234567890")}
    assert device.manufacturer == "Sungrow"
    assert device.name == "Mock Title"


async def test_device_info_no_configuration_url(
    hass: HomeAssistant,
    aioclient_mock: AiohttpClientMocker,
    config_entry: MockConfigEntry,
) -> None:
    """Test device info."""
    aioclient_mock.clear_requests()
    aioclient_mock.get("http://1.1.1.1", exc=ClientConnectorError(Mock(), Mock()))

    await hass.config_entries.async_setup(config_entry.entry_id)
    device_registry = dr.async_get(hass)
    await hass.async_block_till_done()
    device = device_registry.async_get_device({(DOMAIN, "A1234567890")})
    await hass.async_block_till_done()

    assert device is not None
    assert device.configuration_url is None
    assert device.entry_type is None
    assert device.identifiers == {(DOMAIN, "A1234567890")}
    assert device.manufacturer == "Sungrow"
    assert device.name == "Mock Title"


async def test_device_data(hass: HomeAssistant, config_entry: MockConfigEntry) -> None:
    """Test device data."""

    with patch.object(SungrowClient, "refresh", AsyncMock()), patch.object(
        SungrowClient, "data", PropertyMock(return_value=demo_data)
    ):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()
        await hass.data[DOMAIN][config_entry.entry_id].async_refresh()

        sensor = hass.states.get("sensor.mock_title_daily_output_energy")

        assert sensor.state == "42.42"


async def test_device_data_not_available(
    hass: HomeAssistant, config_entry: MockConfigEntry
) -> None:
    """Test device data not available."""

    with patch.object(SungrowClient, "refresh", AsyncMock()):
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        assert hass.data[DOMAIN][config_entry.entry_id].last_update_success is True
    with (
        patch.object(SungrowClient, "refresh", AsyncMock(side_effect=ModbusException)),
        patch.object(
            SungrowClient, "data", PropertyMock(return_value=demo_data)
        ) as data_mock,
    ):
        await hass.data[DOMAIN][config_entry.entry_id].async_refresh()

        assert hass.data[DOMAIN][config_entry.entry_id].last_update_success is False

        data_mock.assert_not_called()
