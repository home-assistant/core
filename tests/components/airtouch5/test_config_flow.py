"""Test the Airtouch 5 config flow."""

import contextlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from homeassistant import config_entries
from homeassistant.components.airtouch5 import async_migrate_entry
from homeassistant.components.airtouch5.config_flow import AirTouch5ConfigFlow
from homeassistant.components.airtouch5.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.device_registry import DeviceRegistry
from homeassistant.helpers.entity_registry import EntityRegistry

from .conftest import CONF_HOST, AirtouchDevice, MockConfigEntry

pytestmark = pytest.mark.usefixtures("mock_setup_entry")


async def test_manual_success(
    hass: HomeAssistant,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test we get the form."""

    host = "1.1.1.1"

    # Create a fake device to return from the mock
    fake_device = AirtouchDevice(
        system_id="12345",
        name="Test Device",
        ip=host,
        model="AT5",
        console_id="abcde",
    )

    with (
        patch.object(
            AirTouch5ConfigFlow,
            "_discover_device_by_ip",
            new_callable=AsyncMock,
            return_value=fake_device,
        ),
        patch.object(
            AirTouch5ConfigFlow,
            "_discovery",
            new_callable=AsyncMock,
            return_value=[fake_device],
        ),
        patch(
            "airtouch5py.airtouch5_simple_client.Airtouch5SimpleClient.test_connection",
            return_value=None,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "choose"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"Select Device": "manual"},
        )

        assert result2["type"] is FlowResultType.FORM
        assert result2["step_id"] == "manual"

        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": host,
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.CREATE_ENTRY
    assert result3["data"]["host"] == host

    assert len(mock_setup_entry.mock_calls) == 1


async def test_manual_connection_exception(
    hass: HomeAssistant, mock_airtouch_discovery: AsyncMock
) -> None:
    """Test we handle cannot connect error."""

    fake_device = AirtouchDevice(
        system_id="12345",
        name="Test Device",
        ip="1.1.1.1",
        model="AT5",
        console_id="abcde",
    )

    with (
        patch.object(
            AirTouch5ConfigFlow,
            "_discover_device_by_ip",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch.object(
            AirTouch5ConfigFlow,
            "_discovery",
            new_callable=AsyncMock,
            return_value=[fake_device],
        ),
        patch(
            "airtouch5py.airtouch5_simple_client.Airtouch5SimpleClient.test_connection",
            side_effect=Exception,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "choose"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"Select Device": "manual"},
        )

        assert result2["type"] is FlowResultType.FORM
        assert result2["step_id"] == "manual"

        result3 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {
                "host": "1.1.1.1",
            },
        )
        await hass.async_block_till_done()

    assert result3["type"] is FlowResultType.FORM
    assert result3["errors"] == {"base": "cannot_connect"}


async def test_select_success(
    hass: HomeAssistant,
    mock_airtouch_discovery: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test we handle device not found error."""

    # Create a fake device to return from the mock
    fake_device = AirtouchDevice(
        system_id="12345",
        name="Test Device",
        ip="1.1.1.1",
        model="AT5",
        console_id="abcde",
    )

    with (
        patch.object(
            AirTouch5ConfigFlow,
            "_discover_device_by_ip",
            new_callable=AsyncMock,
            return_value=fake_device,
        ),
        patch.object(
            AirTouch5ConfigFlow,
            "_discovery",
            new_callable=AsyncMock,
            return_value=[fake_device],
        ),
        patch(
            "airtouch5py.airtouch5_simple_client.Airtouch5SimpleClient.test_connection",
            return_value=None,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "choose"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"Select Device": fake_device.system_id},
        )

        assert result2["type"] is FlowResultType.CREATE_ENTRY
        assert result2["data"]["host"] == fake_device.ip
        assert len(mock_setup_entry.mock_calls) == 1


async def test_select_connection_exception(
    hass: HomeAssistant,
    mock_airtouch_discovery: AsyncMock,
    mock_setup_entry: AsyncMock,
) -> None:
    """Test we handle device not found error."""

    # Create a fake device to return from the mock
    fake_device = AirtouchDevice(
        system_id="12345",
        name="Test Device",
        ip="1.1.1.1",
        model="AT5",
        console_id="abcde",
    )

    with (
        patch.object(
            AirTouch5ConfigFlow,
            "_discover_device_by_ip",
            new_callable=AsyncMock,
            return_value=fake_device,
        ),
        patch.object(
            AirTouch5ConfigFlow,
            "_discovery",
            new_callable=AsyncMock,
            return_value=[fake_device],
        ),
        patch(
            "airtouch5py.airtouch5_simple_client.Airtouch5SimpleClient.test_connection",
            side_effect=Exception,
        ),
    ):
        result = await hass.config_entries.flow.async_init(
            DOMAIN, context={"source": config_entries.SOURCE_USER}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "choose"

        result2 = await hass.config_entries.flow.async_configure(
            result["flow_id"],
            {"Select Device": fake_device.system_id},
        )

        assert result2["type"] is FlowResultType.FORM


async def test_discovery_success() -> None:
    """Test discovery returns devices."""
    flow = AirTouch5ConfigFlow()

    fake_devices = [
        AirtouchDevice(
            system_id="123",
            name="Test",
            ip="1.1.1.1",
            model="AT5",
            console_id="abc",
        )
    ]

    mock_instance = AsyncMock()
    mock_instance.establish_server.return_value = None
    mock_instance.discover.return_value = fake_devices
    mock_instance.close.return_value = None

    with patch(
        "homeassistant.components.airtouch5.config_flow.AirtouchDiscovery",
        return_value=mock_instance,
    ):
        devices = await flow._discovery()

    assert devices == fake_devices
    mock_instance.establish_server.assert_awaited_once()
    mock_instance.discover.assert_awaited_once()
    mock_instance.close.assert_awaited_once()


async def test_discovery_exception_returns_empty() -> None:
    """Test discovery handles exceptions and always closes."""
    flow = AirTouch5ConfigFlow()

    mock_instance = AsyncMock()
    mock_instance.establish_server.side_effect = Exception("boom")
    mock_instance.close.return_value = None

    with patch(
        "homeassistant.components.airtouch5.config_flow.AirtouchDiscovery",
        return_value=mock_instance,
    ):
        devices = await flow._discovery()

    assert devices == []
    mock_instance.close.assert_awaited_once()


async def test_discovery_always_closes() -> None:
    """Test discovery always closes the connection."""
    flow = AirTouch5ConfigFlow()

    mock_instance = AsyncMock()
    mock_instance.establish_server.return_value = None
    mock_instance.discover.side_effect = Exception("fail")
    mock_instance.close.return_value = None

    with patch(
        "homeassistant.components.airtouch5.config_flow.AirtouchDiscovery",
        return_value=mock_instance,
    ):
        await flow._discovery()

    mock_instance.close.assert_awaited_once()


async def test_discover_device_by_ip_success() -> None:
    """Test discover_device_by_ip returns a device."""
    flow = AirTouch5ConfigFlow()

    fake_device = AirtouchDevice(
        system_id="123",
        name="Test",
        ip="1.1.1.1",
        model="AT5",
        console_id="abc",
    )

    mock_instance = AsyncMock()
    mock_instance.establish_server.return_value = None
    mock_instance.discover_by_ip.return_value = fake_device
    mock_instance.close.return_value = None

    with patch(
        "homeassistant.components.airtouch5.config_flow.AirtouchDiscovery",
        return_value=mock_instance,
    ):
        device = await flow._discover_device_by_ip("1.1.1.1")

    assert device == fake_device
    mock_instance.establish_server.assert_awaited_once()
    mock_instance.discover_by_ip.assert_awaited_once_with("1.1.1.1")
    mock_instance.close.assert_awaited_once()


async def test_discover_device_by_ip_none() -> None:
    """Test discover_device_by_ip returns None when device is not found."""
    flow = AirTouch5ConfigFlow()

    mock_instance = AsyncMock()
    mock_instance.establish_server.return_value = None
    mock_instance.discover_by_ip.return_value = None
    mock_instance.close.return_value = None

    with patch(
        "homeassistant.components.airtouch5.config_flow.AirtouchDiscovery",
        return_value=mock_instance,
    ):
        device = await flow._discover_device_by_ip("1.1.1.1")

    assert device is None
    mock_instance.close.assert_awaited_once()


async def test_discover_device_by_ip_exception_closes() -> None:
    """Test discover_device_by_ip handles exceptions and always closes."""
    flow = AirTouch5ConfigFlow()

    mock_instance = AsyncMock()
    mock_instance.establish_server.side_effect = Exception("boom")
    mock_instance.close.return_value = None

    with (
        patch(
            "homeassistant.components.airtouch5.config_flow.AirtouchDiscovery",
            return_value=mock_instance,
        ),
        contextlib.suppress(Exception),
    ):
        await flow._discover_device_by_ip("1.1.1.1")

    mock_instance.close.assert_awaited_once()


async def test_migrate_entry_success(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    device_registry: DeviceRegistry,
) -> None:
    """Test successful migration."""

    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.2.3.4"},
        unique_id="old_id",
        version=1,
        minor_version=1,
    )
    mock_config_entry.add_to_hass(hass)

    # Mock device returned from discovery
    mock_device = MagicMock()
    mock_device.system_id = "sys123"
    mock_device.ip = "1.2.3.4"
    mock_device.model = "model"
    mock_device.console_id = "console"
    mock_device.name = "My AC"

    with patch(
        "homeassistant.components.airtouch5.AirtouchDiscovery"
    ) as mock_discovery:
        instance = mock_discovery.return_value
        instance.establish_server = AsyncMock()
        instance.discover_by_ip = AsyncMock(return_value=mock_device)
        instance.close = AsyncMock()

        # Create an entity to migrate
        entity_entry = entity_registry.async_get_or_create(
            "climate",
            DOMAIN,
            "zone_1",
        )

        result = await async_migrate_entry(hass, mock_config_entry)
        updated = entity_registry.async_get(entity_entry.entity_id)
        assert updated.unique_id == "sys123_1"

    assert result is True

    # Check config entry updated
    assert mock_config_entry.unique_id == "sys123"
    assert mock_config_entry.data["system_id"] == "sys123"
    assert mock_config_entry.minor_version == 2

    # Check entity updated
    updated = entity_registry.async_get(entity_entry.entity_id)
    assert updated.unique_id == "sys123_1"


async def test_migrate_entry_success_AC_unit(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    device_registry: DeviceRegistry,
) -> None:
    """Test successful migration."""

    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.2.3.4"},
        unique_id="old_id",
        version=1,
        minor_version=1,
    )
    mock_config_entry.add_to_hass(hass)

    # Mock device returned from discovery
    mock_device = MagicMock()
    mock_device.system_id = "sys123"
    mock_device.ip = "1.2.3.4"
    mock_device.model = "model"
    mock_device.console_id = "console"
    mock_device.name = "My AC"

    with patch(
        "homeassistant.components.airtouch5.AirtouchDiscovery"
    ) as mock_discovery:
        instance = mock_discovery.return_value
        instance.establish_server = AsyncMock()
        instance.discover_by_ip = AsyncMock(return_value=mock_device)
        instance.close = AsyncMock()

        # Create an entity to migrate
        entity_entry = entity_registry.async_get_or_create(
            "climate",
            DOMAIN,
            "ac_0",
        )

        result = await async_migrate_entry(hass, mock_config_entry)

        updated = entity_registry.async_get(entity_entry.entity_id)

        assert updated.unique_id == "sys123"

    assert result is True

    # Check config entry updated
    assert mock_config_entry.unique_id == "sys123"
    assert mock_config_entry.data["system_id"] == "sys123"
    assert mock_config_entry.minor_version == 2

    # Check entity updated
    updated = entity_registry.async_get(entity_entry.entity_id)
    assert updated.unique_id == "sys123"


async def test_migrate_entry_success_cover(
    hass: HomeAssistant,
    entity_registry: EntityRegistry,
    device_registry: DeviceRegistry,
) -> None:
    """Test successful migration."""

    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.2.3.4"},
        unique_id="old_id",
        version=1,
        minor_version=1,
    )
    mock_config_entry.add_to_hass(hass)

    # Mock device returned from discovery
    mock_device = MagicMock()
    mock_device.system_id = "sys123"
    mock_device.ip = "1.2.3.4"
    mock_device.model = "model"
    mock_device.console_id = "console"
    mock_device.name = "My AC"

    with patch(
        "homeassistant.components.airtouch5.AirtouchDiscovery"
    ) as mock_discovery:
        instance = mock_discovery.return_value
        instance.establish_server = AsyncMock()
        instance.discover_by_ip = AsyncMock(return_value=mock_device)
        instance.close = AsyncMock()

        # Create an entity to migrate
        entity_entry = entity_registry.async_get_or_create(
            "cover",
            DOMAIN,
            "zone_1_open_percentage",
        )

        result = await async_migrate_entry(hass, mock_config_entry)

        updated = entity_registry.async_get(entity_entry.entity_id)

        assert updated.unique_id == "sys123_1_open_percentage"

    assert result is True

    # Check config entry updated
    assert mock_config_entry.unique_id == "sys123"
    assert mock_config_entry.data["system_id"] == "sys123"
    assert mock_config_entry.minor_version == 2

    # Check entity updated
    updated = entity_registry.async_get(entity_entry.entity_id)
    assert updated.unique_id == "sys123_1_open_percentage"


async def test_migrate_entry_timeout(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test migration fails on timeout."""

    mock_config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: "1.2.3.4"},
        unique_id="old_id",
        version=1,
        minor_version=1,
    )
    mock_config_entry.add_to_hass(hass)

    with patch(
        "homeassistant.components.airtouch5.AirtouchDiscovery"
    ) as mock_discovery:
        instance = mock_discovery.return_value
        instance.establish_server = AsyncMock()
        instance.discover_by_ip = AsyncMock(side_effect=TimeoutError)
        instance.close = AsyncMock()

        result = await async_migrate_entry(hass, mock_config_entry)

    assert result is False

    async def test_migrate_entry_noop(
        hass: HomeAssistant,
        mock_config_entry: MockConfigEntry,
    ):
        """Test migration skipped when version not 1."""

        mock_config_entry.minor_version = 2

        result = await async_migrate_entry(hass, mock_config_entry)

        assert result is True

    async def test_migrate_entry_updates_device_registry(
        hass: HomeAssistant,
        mock_config_entry: MockConfigEntry,
        device_registry: DeviceRegistry,
    ):
        """Test device identifiers are updated."""

        mock_config_entry = MockConfigEntry(
            domain=DOMAIN,
            data={CONF_HOST: "1.2.3.4"},
            unique_id="old_id",
            version=1,
            minor_version=1,
        )
        mock_config_entry.add_to_hass(hass)

        device = device_registry.async_get_or_create(
            config_entry_id=mock_config_entry.entry_id,
            identifiers={("airtouch5", "zone_1")},
            name="Zone Device",
        )

        mock_device = MagicMock()
        mock_device.system_id = "sys123"
        mock_device.ip = "1.2.3.4"
        mock_device.model = "model"
        mock_device.console_id = "console"
        mock_device.name = "My AC"

        with patch(
            "homeassistant.components.airtouch5.AirtouchDiscovery"
        ) as mock_discovery:
            instance = mock_discovery.return_value
            instance.establish_server = AsyncMock()
            instance.discover_by_ip = AsyncMock(return_value=mock_device)
            instance.close = AsyncMock()

            await async_migrate_entry(hass, mock_config_entry)

        updated_device = device_registry.async_get(device.id)
        assert ("airtouch5", "sys123_1") in updated_device.identifiers
