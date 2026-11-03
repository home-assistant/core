"""Test init of ecovacs."""

from unittest.mock import Mock, patch

from deebot_client.events import FirmwareEvent, NetworkInfoEvent
from deebot_client.exceptions import (
    DeebotError,
    DeviceVerificationRequiredError,
    InvalidAuthenticationError,
)
from deebot_client.models import AccountCredentials
import pytest
from pytest_homeassistant.common import MockConfigEntry
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.ecovacs.const import CONF_ACCOUNT_CREDENTIALS, DOMAIN
from homeassistant.components.ecovacs.controller import EcovacsController
from homeassistant.config_entries import SOURCE_REAUTH, ConfigEntryState
from homeassistant.const import CONF_DEVICE_ID
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .const import (
    ACCOUNT_CREDENTIALS_DATA,
    CLOUD_DEVICE_ID,
    SELF_HOSTED_DEVICE_ID,
    STORED_ENTRY_DATA_CLOUD,
    VALID_ENTRY_DATA_CLOUD,
    VALID_ENTRY_DATA_SELF_HOSTED,
)
from .util import notify_and_wait


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


@pytest.mark.parametrize(
    ("mock_config_entry_data", "account_credentials"),
    [
        pytest.param(STORED_ENTRY_DATA_CLOUD, None, id="not_stored"),
        pytest.param(
            STORED_ENTRY_DATA_CLOUD | ACCOUNT_CREDENTIALS_DATA,
            AccountCredentials("account_token", "account_user_id"),
            id="stored",
        ),
    ],
)
@pytest.mark.usefixtures("mock_mqtt_client")
async def test_stored_account_credentials_seed_authenticator(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_authenticator_class: Mock,
    account_credentials: AccountCredentials | None,
) -> None:
    """Test the authenticator starts from the stored account credentials."""
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    assert (
        mock_authenticator_class.call_args.kwargs["account_credentials"]
        == account_credentials
    )


@pytest.mark.usefixtures("mock_mqtt_client")
async def test_new_account_credentials_are_stored(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_authenticator: Mock,
) -> None:
    """Test new account credentials of the authenticator are stored in the entry."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    store_account_credentials = (
        mock_authenticator.subscribe_account_credentials.call_args.args[0]
    )
    await store_account_credentials(AccountCredentials("new_token", "new_user_id"))

    assert mock_config_entry.data == STORED_ENTRY_DATA_CLOUD | {
        CONF_ACCOUNT_CREDENTIALS: {
            "access_token": "new_token",
            "user_id": "new_user_id",
        }
    }


@pytest.mark.usefixtures("mock_mqtt_client")
async def test_unload_unsubscribes_account_credentials(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_authenticator: Mock,
) -> None:
    """Test unloading stops storing new account credentials."""
    mock_config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    mock_authenticator.subscribe_account_credentials.return_value.assert_called_once()


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


async def test_device_info_updated_from_events(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    controller: EcovacsController,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test reported firmware and MAC update the device registry."""
    device = controller.devices[0]
    identifier = (DOMAIN, device.device_info["did"])

    await notify_and_wait(hass, device.events, FirmwareEvent("1.2.3"))
    await notify_and_wait(
        hass,
        device.events,
        NetworkInfoEvent("192.168.0.10", "Testnetwork", -62, "AA:BB:CC:DD:EE:FF"),
    )

    device_entry = device_registry.async_get_device_by_identifier(
        identifier, mock_config_entry.entry_id
    )
    assert device_entry
    assert device_entry.sw_version == "1.2.3"
    assert device_entry.connections == {
        (dr.CONNECTION_NETWORK_MAC, "aa:bb:cc:dd:ee:ff")
    }

    # After a reload the firmware is unknown until reported again
    assert await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    device_entry = device_registry.async_get_device_by_identifier(
        identifier, mock_config_entry.entry_id
    )
    assert device_entry
    assert device_entry.sw_version == "1.2.3"


@pytest.mark.usefixtures(
    "entity_registry_enabled_by_default", "mock_vacbot", "init_integration"
)
@pytest.mark.parametrize(
    ("device_fixture", "entities"),
    [
        ("yna5x1", 27),
        ("5xu9h3", 25),
        ("twunby", 53),
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
