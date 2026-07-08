"""Test for airOS integration setup."""

from unittest.mock import ANY, AsyncMock, MagicMock, patch

from airos.exceptions import (
    AirOSConnectionAuthenticationError,
    AirOSConnectionSetupError,
    AirOSDeviceConnectionError,
    AirOSKeyDataMissingError,
)
import pytest

from homeassistant.components.airos.const import (
    CONF_LEGACY_SSL,
    DEFAULT_SSL,
    DEFAULT_VERIFY_SSL,
    DOMAIN,
    SECTION_ADDITIONAL_SETTINGS,
)
from homeassistant.components.airos.coordinator import async_fetch_airos_data
from homeassistant.components.binary_sensor import DOMAIN as BINARY_SENSOR_DOMAIN
from homeassistant.components.sensor import DOMAIN as SENSOR_DOMAIN
from homeassistant.config_entries import (
    SOURCE_USER,
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    ConfigEntryState,
)
from homeassistant.const import (
    CONF_HOST,
    CONF_PASSWORD,
    CONF_SSL,
    CONF_USERNAME,
    CONF_VERIFY_SSL,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry

MOCK_CONFIG_V1 = {
    CONF_HOST: "1.1.1.1",
    CONF_USERNAME: "ubnt",
    CONF_PASSWORD: "test-password",
}

MOCK_CONFIG_PLAIN = {
    CONF_HOST: "1.1.1.1",
    CONF_USERNAME: "ubnt",
    CONF_PASSWORD: "test-password",
    SECTION_ADDITIONAL_SETTINGS: {
        CONF_SSL: False,
        CONF_VERIFY_SSL: False,
    },
}

MOCK_CONFIG_V1_2 = {
    CONF_HOST: "1.1.1.1",
    CONF_USERNAME: "ubnt",
    CONF_PASSWORD: "test-password",
    "advanced_settings": {
        CONF_SSL: DEFAULT_SSL,
        CONF_VERIFY_SSL: DEFAULT_VERIFY_SSL,
    },
}

MOCK_CONFIG_V2_1 = {
    CONF_HOST: "1.1.1.1",
    CONF_USERNAME: "ubnt",
    CONF_PASSWORD: "test-password",
    "advanced_settings": {
        CONF_SSL: DEFAULT_SSL,
        CONF_VERIFY_SSL: DEFAULT_VERIFY_SSL,
    },
}

MOCK_CONFIG_V3_1 = {
    CONF_HOST: "1.1.1.1",
    CONF_USERNAME: "ubnt",
    CONF_PASSWORD: "test-password",
    SECTION_ADDITIONAL_SETTINGS: {
        CONF_SSL: DEFAULT_SSL,
        CONF_VERIFY_SSL: DEFAULT_VERIFY_SSL,
    },
}


async def test_setup_entry_with_default_ssl(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_airos_class: MagicMock,
    mock_airos_client: MagicMock,
    mock_async_get_firmware_data: AsyncMock,
) -> None:
    """Test setting up a config entry with default SSL options."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    mock_airos_class.assert_called_once_with(
        host=mock_config_entry.data[CONF_HOST],
        username=mock_config_entry.data[CONF_USERNAME],
        password=mock_config_entry.data[CONF_PASSWORD],
        session=ANY,
        use_ssl=DEFAULT_SSL,
    )

    assert mock_config_entry.data[SECTION_ADDITIONAL_SETTINGS][CONF_SSL] is True
    assert mock_config_entry.data[SECTION_ADDITIONAL_SETTINGS][CONF_VERIFY_SSL] is False


async def test_setup_entry_without_ssl(
    hass: HomeAssistant,
    mock_airos_class: MagicMock,
    mock_airos_client: MagicMock,
    mock_async_get_firmware_data: AsyncMock,
) -> None:
    """Test setting up a config entry adjusted to plain HTTP."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG_PLAIN,
        entry_id="1",
        unique_id="airos_device",
        version=2,
        minor_version=2,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED

    mock_airos_class.assert_called_once_with(
        host=entry.data[CONF_HOST],
        username=entry.data[CONF_USERNAME],
        password=entry.data[CONF_PASSWORD],
        session=ANY,
        use_ssl=False,
    )

    assert entry.data[SECTION_ADDITIONAL_SETTINGS][CONF_SSL] is False
    assert entry.data[SECTION_ADDITIONAL_SETTINGS][CONF_VERIFY_SSL] is False


async def test_ssl_migrate_entry(
    hass: HomeAssistant,
    mock_airos_client: MagicMock,
    mock_async_get_firmware_data: AsyncMock,
) -> None:
    """Test migrate entry SSL options."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=MOCK_CONFIG_V1,
        entry_id="1",
        unique_id="airos_device",
        version=1,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.version == 3
    assert entry.minor_version == 1
    assert entry.data == MOCK_CONFIG_V3_1


@pytest.mark.parametrize(
    ("sensor_domain", "sensor_name", "mock_id"),
    [
        (BINARY_SENSOR_DOMAIN, "port_forwarding", "device_id_12345"),
        (SENSOR_DOMAIN, "antenna_gain", "01:23:45:67:89:ab"),
    ],
)
async def test_uid_migrate_entry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    sensor_domain: str,
    sensor_name: str,
    mock_id: str,
    mock_airos_client: MagicMock,
    mock_async_get_firmware_data: AsyncMock,
) -> None:
    """Test migrate entry unique id."""
    entity_registry = er.async_get(hass)

    MOCK_MAC = dr.format_mac("01:23:45:67:89:AB")
    MOCK_ID = "device_id_12345"
    old_unique_id = f"{mock_id}_{sensor_name}"
    new_unique_id = f"{MOCK_MAC}_{sensor_name}"

    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=MOCK_CONFIG_V1_2,
        entry_id="1",
        unique_id=mock_id,
        version=1,
        minor_version=2,
    )
    entry.add_to_hass(hass)

    device_registry.async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, MOCK_ID)},
        connections={
            (dr.CONNECTION_NETWORK_MAC, MOCK_MAC),
        },
    )
    await hass.async_block_till_done()

    old_entity_entry = entity_registry.async_get_or_create(
        DOMAIN, sensor_domain, old_unique_id, config_entry=entry
    )
    original_entity_id = old_entity_entry.entity_id

    hass.config_entries.async_update_entry(entry, unique_id=MOCK_MAC)
    await hass.async_block_till_done()

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    updated_entity_entry = entity_registry.async_get(original_entity_id)

    assert entry.state is ConfigEntryState.LOADED
    assert entry.version == 3
    assert entry.minor_version == 1
    assert (
        entity_registry.async_get_entity_id(sensor_domain, DOMAIN, old_unique_id)
        is None
    )
    assert updated_entity_entry.unique_id == new_unique_id


async def test_migrate_additional_settings(
    hass: HomeAssistant,
    mock_airos_client: MagicMock,
    mock_async_get_firmware_data: AsyncMock,
) -> None:
    """Test rename advanced_settings."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=MOCK_CONFIG_V2_1,
        entry_id="1",
        unique_id="airos_device",
        version=2,
        minor_version=1,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.LOADED
    assert entry.version == 3
    assert entry.minor_version == 1
    assert entry.data == MOCK_CONFIG_V3_1


async def test_migrate_future_return(
    hass: HomeAssistant,
    mock_airos_client: MagicMock,
    mock_async_get_firmware_data: AsyncMock,
) -> None:
    """Test migrate entry unique id."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        source=SOURCE_USER,
        data=MOCK_CONFIG_V1_2,
        entry_id="1",
        unique_id="airos_device",
        version=4,
    )
    entry.add_to_hass(hass)

    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.state is ConfigEntryState.MIGRATION_ERROR


async def test_load_unload_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_airos_client: MagicMock,
    mock_async_get_firmware_data: AsyncMock,
) -> None:
    """Test setup and unload config entry."""
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.LOADED

    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.mark.parametrize(
    ("exception", "state"),
    [
        (AirOSConnectionAuthenticationError, ConfigEntryState.SETUP_ERROR),
        (AirOSConnectionSetupError, ConfigEntryState.SETUP_RETRY),
        (AirOSDeviceConnectionError, ConfigEntryState.SETUP_RETRY),
        (AirOSKeyDataMissingError, ConfigEntryState.SETUP_ERROR),
        (Exception, ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_setup_entry_failure(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_airos_class: MagicMock,
    mock_airos_client: MagicMock,
    mock_async_get_firmware_data: AsyncMock,
    exception: Exception,
    state: ConfigEntryState,
) -> None:
    """Test config entry setup failure."""
    mock_async_get_firmware_data.side_effect = exception

    mock_config_entry.add_to_hass(hass)

    result = await hass.config_entries.async_setup(mock_config_entry.entry_id)
    assert result is False
    assert mock_config_entry.state is state


async def test_fetch_airos_data_auth_error(mock_airos_client: MagicMock) -> None:
    """Test login auth error triggers ConfigEntryAuthFailed."""
    mock_airos_client.login.side_effect = AirOSConnectionAuthenticationError

    with pytest.raises(ConfigEntryAuthFailed):
        await async_fetch_airos_data(mock_airos_client, mock_airos_client.status)


async def test_setup_entry_with_legacy_ssl(
    hass: HomeAssistant,
    mock_airos_class: MagicMock,
    mock_airos_client: MagicMock,
    mock_async_get_firmware_data: AsyncMock,
) -> None:
    """Test setting up a config entry with legacy SSL session ownership."""
    legacy_entry = MockConfigEntry(
        domain=DOMAIN,
        title="NanoStation",
        unique_id="01:23:45:67:89:AB",
        data={**MOCK_CONFIG_V3_1, CONF_LEGACY_SSL: True},
    )
    legacy_entry.add_to_hass(hass)

    legacy_session = MagicMock()
    legacy_session.close = AsyncMock()

    with (
        patch(
            "homeassistant.components.airos.ClientSession",
            return_value=legacy_session,
        ) as mock_client_session,
        patch(
            "homeassistant.components.airos.TCPConnector",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.airos.build_legacy_context",
            return_value=MagicMock(),
        ) as mock_build_legacy_context,
    ):
        await hass.config_entries.async_setup(legacy_entry.entry_id)
        await hass.async_block_till_done()

        assert legacy_entry.state is ConfigEntryState.LOADED

        mock_client_session.assert_called_once()
        mock_build_legacy_context.assert_called_once_with(verify_ssl=DEFAULT_VERIFY_SSL)

        mock_airos_class.assert_called_once_with(
            host=MOCK_CONFIG_V3_1[CONF_HOST],
            username=MOCK_CONFIG_V3_1[CONF_USERNAME],
            password=MOCK_CONFIG_V3_1[CONF_PASSWORD],
            session=legacy_session,
            use_ssl=DEFAULT_SSL,
        )

        assert await hass.config_entries.async_unload(legacy_entry.entry_id)
        await hass.async_block_till_done()

    legacy_session.close.assert_awaited_once()


@pytest.mark.parametrize(
    ("exception", "state"),
    [
        (AirOSDeviceConnectionError, ConfigEntryState.SETUP_RETRY),
    ],
)
async def test_setup_entry_with_legacy_ssl_fails_firmware_detect(
    hass: HomeAssistant,
    mock_airos_class: MagicMock,
    mock_airos_client: MagicMock,
    mock_async_get_firmware_data: AsyncMock,
    exception: Exception,
    state: ConfigEntryState,
) -> None:
    """Test handling legacy SSL connection failure."""
    legacy_entry = MockConfigEntry(
        domain=DOMAIN,
        title="NanoStation",
        unique_id="01:23:45:67:89:AB",
        data={**MOCK_CONFIG_V3_1, CONF_LEGACY_SSL: True},
    )
    legacy_entry.add_to_hass(hass)

    legacy_session = MagicMock()
    legacy_session.close = AsyncMock()

    mock_async_get_firmware_data.side_effect = exception

    with (
        patch(
            "homeassistant.components.airos.ClientSession",
            return_value=legacy_session,
        ) as mock_client_session,
        patch(
            "homeassistant.components.airos.TCPConnector",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.airos.build_legacy_context",
            return_value=MagicMock(),
        ) as mock_build_legacy_context,
    ):
        result = await hass.config_entries.async_setup(legacy_entry.entry_id)
        await hass.async_block_till_done()

    assert result is False
    assert legacy_entry.state is state
    mock_client_session.assert_called_once()
    mock_build_legacy_context.assert_called_once_with(verify_ssl=DEFAULT_VERIFY_SSL)
    legacy_session.close.assert_awaited_once()


@pytest.mark.parametrize(
    ("exception", "state"),
    [
        (ConfigEntryNotReady, ConfigEntryState.SETUP_RETRY),
        (Exception, ConfigEntryState.SETUP_ERROR),
    ],
)
async def test_setup_entry_with_legacy_ssl_fails_coordinator(
    hass: HomeAssistant,
    mock_airos_class: MagicMock,
    mock_airos_client: MagicMock,
    mock_async_get_firmware_data: AsyncMock,
    exception: Exception,
    state: ConfigEntryState,
) -> None:
    """Test legacy session is closed when status coordinator first refresh fails."""
    legacy_entry = MockConfigEntry(
        domain=DOMAIN,
        title="NanoStation",
        unique_id="01:23:45:67:89:AB",
        data={**MOCK_CONFIG_V1_2, CONF_LEGACY_SSL: True},
    )
    legacy_entry.add_to_hass(hass)

    legacy_session = MagicMock()
    legacy_session.close = AsyncMock()

    mock_status_coordinator = MagicMock()
    mock_status_coordinator.async_config_entry_first_refresh = AsyncMock(
        side_effect=exception
    )

    with (
        patch(
            "homeassistant.components.airos.ClientSession",
            return_value=legacy_session,
        ) as mock_client_session,
        patch(
            "homeassistant.components.airos.TCPConnector",
            return_value=MagicMock(),
        ),
        patch(
            "homeassistant.components.airos.build_legacy_context",
            return_value=MagicMock(),
        ) as mock_build_legacy_context,
        patch(
            "homeassistant.components.airos.AirOSDataUpdateCoordinator",
            return_value=mock_status_coordinator,
        ),
    ):
        result = await hass.config_entries.async_setup(legacy_entry.entry_id)
        await hass.async_block_till_done()

    assert result is False
    assert legacy_entry.state is state
    mock_client_session.assert_called_once()
    mock_build_legacy_context.assert_called_once_with(verify_ssl=DEFAULT_VERIFY_SSL)
    legacy_session.close.assert_awaited_once()
