"""Tests for the init module of the Easywave Core integration."""

from unittest.mock import AsyncMock, patch

from homeassistant.components.easywave import async_remove_config_entry_device
from homeassistant.components.easywave.const import DOMAIN
from homeassistant.components.easywave.coordinator import EasywaveCoordinator
from homeassistant.components.easywave.devices import get_devices
from homeassistant.const import CONF_DEVICE_ID, CONF_DEVICES
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, issue_registry as ir

from .conftest import (
    MOCK_ENTRY_DATA,
    MOCK_ENTRY_ID,
    MOCK_NEO_SENSOR_DEVICE_ID,
    MOCK_TRANSMITTER_DEVICE_ID,
    _devices_options,
    _neo_sensor_device_record,
    _transmitter_device_record,
    async_setup_easywave_entry,
    mock_easywave_transceiver,
)

from tests.common import MockConfigEntry


async def test_setup_entry_success(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test successful setup wires a real coordinator and gateway device."""
    transceiver = mock_easywave_transceiver()
    await async_setup_easywave_entry(hass, mock_config_entry, transceiver)

    coordinator = mock_config_entry.runtime_data.coordinator
    assert isinstance(coordinator, EasywaveCoordinator)
    transceiver.connect.assert_awaited_once()

    device = dr.async_get(hass).async_get_device(
        identifiers={(DOMAIN, mock_config_entry.entry_id)}
    )
    assert device is not None
    assert device.hw_version == "1.0"
    assert device.sw_version == "2.0"


async def test_setup_entry_country_allowed(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup succeeds with allowed country."""
    await async_setup_easywave_entry(hass, mock_config_entry, country="FR")


async def test_setup_entry_country_not_allowed(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup returns False for disallowed country."""
    mock_config_entry.add_to_hass(hass)
    hass.config.country = "US"

    result = await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert result is False


async def test_setup_entry_creates_repair_issue(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test repair issue created when country is not allowed."""
    mock_config_entry.add_to_hass(hass)
    hass.config.country = "US"

    result = await hass.config_entries.async_setup(mock_config_entry.entry_id)

    assert result is False
    issues = ir.async_get(hass)
    issue = issues.async_get_issue(
        DOMAIN, f"frequency_not_permitted_{mock_config_entry.entry_id}"
    )
    assert issue is not None
    assert issue.translation_key == "frequency_not_permitted"


async def test_setup_entry_deletes_stale_repair_issue(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test stale repair issue is removed on successful setup."""
    await async_setup_easywave_entry(hass, mock_config_entry)

    issues = ir.async_get(hass)
    issue = issues.async_get_issue(
        DOMAIN, f"frequency_not_permitted_{mock_config_entry.entry_id}"
    )
    assert issue is None


async def test_setup_entry_no_country(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test setup succeeds when no country is configured."""
    await async_setup_easywave_entry(hass, mock_config_entry, country=None)


async def test_unload_entry(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Test unload of config entry shuts down the coordinator and transceiver."""
    transceiver = mock_easywave_transceiver()
    await async_setup_easywave_entry(hass, mock_config_entry, transceiver)
    transceiver.dispose.reset_mock()

    with patch.object(hass.config_entries, "async_unload_platforms", return_value=True):
        result = await hass.config_entries.async_unload(mock_config_entry.entry_id)

    assert result is True
    assert transceiver.dispose.await_count >= 1


async def test_remove_config_entry_device_rejects_gateway(
    hass: HomeAssistant,
) -> None:
    """Removing the RX11 gateway device must be denied."""
    entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        data=MOCK_ENTRY_DATA,
        unique_id="easywave_gw",
    )
    entry.add_to_hass(hass)

    device_registry = dr.async_get(hass)
    gateway_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name="RX11 USB Transceiver",
    )

    result = await async_remove_config_entry_device(hass, entry, gateway_device)
    assert result is False
    assert not entry.subentries


async def test_remove_config_entry_device_removes_child(
    hass: HomeAssistant,
) -> None:
    """Removing a child device via the three-dot menu should succeed."""
    entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        entry_id=MOCK_ENTRY_ID,
        data=MOCK_ENTRY_DATA,
        unique_id="easywave_gw",
        options=_devices_options(
            _neo_sensor_device_record(title="Neo Sensor"),
            _transmitter_device_record(title="Transmitter"),
        ),
    )
    entry.add_to_hass(hass)

    device_registry = dr.async_get(hass)
    child_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, MOCK_NEO_SENSOR_DEVICE_ID)},
        name="Neo Sensor",
    )

    result = await async_remove_config_entry_device(hass, entry, child_device)
    assert result is True
    entry = hass.config_entries.async_get_entry(entry.entry_id)
    assert entry is not None
    devices = entry.options[CONF_DEVICES]
    assert len(devices) == 1
    assert devices[0][CONF_DEVICE_ID] == MOCK_TRANSMITTER_DEVICE_ID


async def test_get_devices_returns_configured_devices(
    hass: HomeAssistant,
) -> None:
    """Test get_devices returns configured devices from options."""
    entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        entry_id=MOCK_ENTRY_ID,
        data=MOCK_ENTRY_DATA,
        unique_id="easywave_gw",
        options=_devices_options(
            _neo_sensor_device_record(title="Neo Sensor"),
            _transmitter_device_record(title="Transmitter"),
        ),
    )
    entry.add_to_hass(hass)

    devices = get_devices(entry)
    assert len(devices) == 2
    assert {device.device_id for device in devices} == {
        MOCK_NEO_SENSOR_DEVICE_ID,
        MOCK_TRANSMITTER_DEVICE_ID,
    }
    assert {device.title for device in devices} == {"Neo Sensor", "Transmitter"}


async def test_options_update_triggers_reload(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Changing device options reloads the config entry."""
    await async_setup_easywave_entry(hass, mock_config_entry)

    with patch.object(
        hass.config_entries, "async_reload", new=AsyncMock()
    ) as mock_reload:
        for listener in mock_config_entry.update_listeners:
            await listener(hass, mock_config_entry)

    mock_reload.assert_awaited_once_with(mock_config_entry.entry_id)


async def test_remove_config_entry_device_rejects_unknown_identifier(
    hass: HomeAssistant,
) -> None:
    """Devices without an Easywave identifier cannot be removed."""
    entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        data=MOCK_ENTRY_DATA,
        unique_id="easywave_gw",
    )
    entry.add_to_hass(hass)

    device_registry = dr.async_get(hass)
    other_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={("other", "device")},
        name="Other Device",
    )

    assert await async_remove_config_entry_device(hass, entry, other_device) is False


async def test_remove_config_entry_device_rejects_orphan_device(
    hass: HomeAssistant,
) -> None:
    """Devices not stored in options cannot be removed."""
    entry = MockConfigEntry(
        version=1,
        domain=DOMAIN,
        entry_id=MOCK_ENTRY_ID,
        data=MOCK_ENTRY_DATA,
        unique_id="easywave_gw",
        options=_devices_options(_transmitter_device_record()),
    )
    entry.add_to_hass(hass)

    device_registry = dr.async_get(hass)
    orphan_device = device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, "unknown_device")},
        name="Unknown",
    )

    assert await async_remove_config_entry_device(hass, entry, orphan_device) is False
