"""Test init of ecovacs."""

from unittest.mock import Mock, patch

from deebot_client.exceptions import (
    DeebotError,
    DeviceVerificationRequiredError,
    InvalidAuthenticationError,
)
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.ecovacs.const import DOMAIN
from homeassistant.components.ecovacs.controller import EcovacsController
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import (
    CLOUD_DEVICE_ID,
    SELF_HOSTED_DEVICE_ID,
    VALID_ENTRY_DATA_CLOUD,
    VALID_ENTRY_DATA_SELF_HOSTED,
)

from tests.common import MockConfigEntry


@pytest.mark.usefixtures(
    "mock_authenticator", "mock_mqtt_client", "mock_device_execute"
)
async def test_load_unload_config_entry(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test loading and unloading the integration."""
    with patch(
        "homeassistant.components.ecovacs.EcovacsController",
        autospec=True,
    ):
        mock_config_entry.add_to_hass(hass)

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        assert mock_config_entry.state is ConfigEntryState.LOADED
        assert DOMAIN not in hass.data
        controller = mock_config_entry.runtime_data
        assert isinstance(controller, EcovacsController)
        controller.initialize.assert_called_once()

        await hass.config_entries.async_unload(mock_config_entry.entry_id)
        await hass.async_block_till_done()
        controller.teardown.assert_called_once()

        assert mock_config_entry.state is ConfigEntryState.NOT_LOADED


@pytest.fixture
def mock_api_client(mock_authenticator: Mock) -> Mock:
    """Mock the API client."""
    with patch(
        "homeassistant.components.ecovacs.controller.ApiClient",
        autospec=True,
    ) as mock_api_client:
        yield mock_api_client.return_value


async def test_config_entry_not_ready(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: Mock,
) -> None:
    """Test the Ecovacs configuration entry not ready."""
    mock_api_client.get_devices.side_effect = DeebotError

    mock_config_entry.add_to_hass(hass)
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_RETRY


@pytest.mark.parametrize(
    "side_effect",
    [
        InvalidAuthenticationError,
        DeviceVerificationRequiredError,
    ],
    ids=["invalid_auth", "device_verification_required"],
)
async def test_auth_failed(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_api_client: Mock,
    side_effect: type[Exception],
) -> None:
    """Test an auth error during setup triggers reauthentication."""
    mock_api_client.get_devices.side_effect = side_effect
    mock_config_entry.add_to_hass(hass)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert mock_config_entry.state is ConfigEntryState.SETUP_ERROR
    flows = hass.config_entries.flow.async_progress_by_handler(DOMAIN)
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH
    assert flows[0]["context"]["entry_id"] == mock_config_entry.entry_id


@pytest.mark.parametrize(
    ("entry_data", "device_id"),
    [
        (VALID_ENTRY_DATA_CLOUD, CLOUD_DEVICE_ID),
        (VALID_ENTRY_DATA_SELF_HOSTED, SELF_HOSTED_DEVICE_ID),
    ],
    ids=["cloud", "self_hosted"],
)
@pytest.mark.usefixtures("mock_authenticator", "mock_mqtt_client", "mock_device_id")
async def test_migrate_entry(
    hass: HomeAssistant,
    entry_data: dict[str, str],
    device_id: str,
) -> None:
    """Test the client device ID is added to an entry created before it was stored."""
    entry = MockConfigEntry(domain=DOMAIN, data=entry_data, minor_version=1)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.version == 1
    assert entry.minor_version == 2
    assert entry.data == entry_data | {CONF_DEVICE_ID: device_id}


@pytest.mark.usefixtures("mock_authenticator", "mock_mqtt_client")
async def test_migrate_entry_keeps_device_id(
    hass: HomeAssistant,
) -> None:
    """Test an already stored client device ID is not replaced."""
    entry_data = VALID_ENTRY_DATA_CLOUD | {CONF_DEVICE_ID: "STOREDID"}
    entry = MockConfigEntry(domain=DOMAIN, data=entry_data, minor_version=1)
    entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    assert entry.minor_version == 2
    assert entry.data == entry_data


async def test_devices_in_dr(
    device_registry: dr.DeviceRegistry,
    controller: EcovacsController,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test all devices are in the device registry."""
    for device in controller.devices:
        assert (
            device_entry := device_registry.async_get_device_by_identifier(
                (DOMAIN, device.device_info["did"]), mock_config_entry.entry_id
            )
        )
        assert device_entry == snapshot(name=device.device_info["did"])


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_vacbot", "init_integration"
)
@pytest.mark.parametrize(
    ("device_fixture", "entities"),
    [
        ("yna5x1", 27),
        ("5xu9h3", 25),
        ("123", 3),
    ],
)
async def test_all_entities_loaded(
    hass: HomeAssistant,
    device_fixture: str,
    entities: int,
) -> None:
    """Test that all entities are loaded together."""
    assert hass.states.async_entity_ids_count() == entities, (
        f"loaded entities for {device_fixture}: {hass.states.async_entity_ids()}"
    )
