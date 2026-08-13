"""Test the Teslemetry energy site local Powerwall routing and pairing flow."""

from collections.abc import Generator
from copy import deepcopy
from types import MappingProxyType
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from aiohttp import ClientError
from aiopowerwall import (
    DEFAULT_GATEWAY_HOST,
    PowerwallAuthenticationError,
    PowerwallConnectionError,
    PowerwallError,
    PowerwallFaultError,
)
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import pytest
from tesla_fleet_api.const import AuthorizedClientState
from tesla_fleet_api.exceptions import InvalidResponse
from tesla_fleet_api.tesla import EnergySiteRouter
from tesla_fleet_api.teslemetry import EnergySite
from tesla_fleet_api.teslemetry.energysite import AuthorizedClient, AuthorizedClients

from homeassistant.components.teslemetry import _async_get_rsa_key_pem
from homeassistant.components.teslemetry.const import (
    CONF_SITE_ID,
    DOMAIN,
    SUBENTRY_TYPE_ENERGY_SITE,
)
from homeassistant.config_entries import (
    ConfigSubentry,
    ConfigSubentryData,
    SubentryFlowResult,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import device_registry as dr

from . import mock_config_entry
from .const import METADATA, METADATA_NOSCOPE, PRODUCTS

from tests.common import MockConfigEntry

SITE_ID = 123456
WALL_CONNECTOR_SITE_ID = 555555
HOST = "192.168.91.1"
PASSWORD = "abcde"
# Matches the paired site's `gateway_id` in the products fixture.
GATEWAY_DIN = "ABC123"
PUBLIC_KEY_DER = b"public-key-der"
PUBLIC_KEY_B64 = "cHVibGljLWtleS1kZXI="

# aiopowerwall's PowerwallClient parses the PEM at construction time, so tests
# that build one need a real (if undersized, for speed) RSA key rather than
# arbitrary bytes.
_TEST_RSA_KEY_PEM = rsa.generate_private_key(
    public_exponent=65537, key_size=1024
).private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.TraditionalOpenSSL,
    encryption_algorithm=serialization.NoEncryption(),
)


def _entry_with_powerwall() -> MockConfigEntry:
    """Return a config entry whose energy site subentry is already paired."""
    entry = mock_config_entry()
    return MockConfigEntry(
        domain=entry.domain,
        version=entry.version,
        minor_version=entry.minor_version,
        unique_id=entry.unique_id,
        data=dict(entry.data),
        subentries_data=[
            ConfigSubentryData(
                subentry_type=SUBENTRY_TYPE_ENERGY_SITE,
                unique_id=str(SITE_ID),
                title="Energy Site",
                data={
                    CONF_SITE_ID: SITE_ID,
                    CONF_HOST: HOST,
                    CONF_PASSWORD: PASSWORD,
                },
            )
        ],
    )


@pytest.fixture(autouse=True)
def mock_gateway_discovery() -> Generator[AsyncMock]:
    """Default gateway-address discovery to no result."""
    with patch(
        "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.find_gateway_address",
        new=AsyncMock(return_value=None),
    ) as mock_find:
        yield mock_find


@pytest.fixture
def mock_rsa_key() -> Generator[None]:
    """Mock RSA key generation/loading, avoiding real crypto and disk I/O."""
    with (
        patch(
            "homeassistant.components.teslemetry.config_flow.Teslemetry.get_rsa_private_key",
            new=AsyncMock(),
        ),
        patch(
            "homeassistant.components.teslemetry.config_flow.Teslemetry.rsa_public_der_pkcs1",
            new_callable=PropertyMock,
            return_value=PUBLIC_KEY_DER,
        ),
        patch(
            "homeassistant.components.teslemetry.config_flow.Teslemetry.rsa_public_der_pkcs1_b64",
            new_callable=PropertyMock,
            return_value=PUBLIC_KEY_B64,
        ),
        patch(
            "homeassistant.components.teslemetry.config_flow.Path.read_bytes",
            return_value=_TEST_RSA_KEY_PEM,
        ),
    ):
        yield


def _mock_powerwall_client(
    *,
    connect_error: Exception | None = None,
    din: str = GATEWAY_DIN,
    status_error: Exception | None = None,
) -> MagicMock:
    """Return a mock aiopowerwall PowerwallClient async context manager."""
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.connect = AsyncMock(return_value=din, side_effect=connect_error)
    client.get_status = AsyncMock(side_effect=status_error)
    return client


def _own_key_clients(
    state: AuthorizedClientState | int | str | None,
) -> AuthorizedClients:
    """Return a typed client list carrying our key in the given state."""
    return AuthorizedClients(
        clients=[
            AuthorizedClient(
                public_key="some-other-key",
                state=AuthorizedClientState.VERIFIED,
                roles=None,
                verification=None,
                raw={},
            ),
            AuthorizedClient(
                public_key=PUBLIC_KEY_B64,
                state=state,
                roles=None,
                verification=None,
                raw={},
            ),
        ],
        raw=None,
    )


def _empty_clients() -> AuthorizedClients:
    """Return a typed client list that is authoritatively empty."""
    return AuthorizedClients(clients=[], raw=None)


async def test_energy_site_router_with_powerwall(hass: HomeAssistant) -> None:
    """A paired energy site wraps its cloud API in an EnergySiteRouter."""
    entry = _entry_with_powerwall()
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.teslemetry._async_get_rsa_key_pem",
            return_value=_TEST_RSA_KEY_PEM,
        ),
        patch("homeassistant.components.teslemetry.PLATFORMS", []),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    energysite = entry.runtime_data.energysites[0]
    assert isinstance(energysite.api, EnergySiteRouter)


async def test_energy_site_cloud_without_powerwall(hass: HomeAssistant) -> None:
    """An energy site without paired credentials keeps the plain cloud API."""
    entry = mock_config_entry()
    entry.add_to_hass(hass)

    with patch("homeassistant.components.teslemetry.PLATFORMS", []):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    energysite = entry.runtime_data.energysites[0]
    assert isinstance(energysite.api, EnergySite)
    assert not isinstance(energysite.api, EnergySiteRouter)


def _entry_with_unpaired_subentry() -> MockConfigEntry:
    """Return a config entry whose energy site subentry exists but is unpaired."""
    entry = mock_config_entry()
    return MockConfigEntry(
        domain=entry.domain,
        version=entry.version,
        minor_version=entry.minor_version,
        unique_id=entry.unique_id,
        data=dict(entry.data),
        subentries_data=[
            ConfigSubentryData(
                subentry_type=SUBENTRY_TYPE_ENERGY_SITE,
                unique_id=str(SITE_ID),
                title="Energy Site",
                data={CONF_SITE_ID: SITE_ID},
            )
        ],
    )


async def _start_add_flow_select_site(
    hass: HomeAssistant, entry: MockConfigEntry
) -> SubentryFlowResult:
    """Start the add flow and select the battery site, returning the next step."""
    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_ENERGY_SITE),
        context={"source": "user"},
    )
    assert result["step_id"] == "user"
    return await hass.config_entries.subentries.async_configure(
        result["flow_id"], {CONF_SITE_ID: str(SITE_ID)}
    )


@pytest.mark.usefixtures("mock_rsa_key")
async def test_subentry_pairing_requires_key_approval(hass: HomeAssistant) -> None:
    """Pairing registers the key, then advances to credentials once approved."""
    entry = await _setup_account_no_subentry(hass)

    client = _mock_powerwall_client()
    with (
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.find_authorized_clients",
            new=AsyncMock(
                side_effect=[
                    _empty_clients(),
                    _own_key_clients(AuthorizedClientState.PENDING_VERIFICATION),
                    _own_key_clients(AuthorizedClientState.VERIFIED),
                ]
            ),
        ),
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.add_authorized_client",
            new=AsyncMock(),
        ) as mock_add,
        patch(
            "homeassistant.components.teslemetry.config_flow.PowerwallClient",
            return_value=client,
        ),
        patch.object(hass.config_entries, "async_schedule_reload"),
    ):
        result = await _start_add_flow_select_site(hass, entry)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "pair"
        mock_add.assert_awaited_once()

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "pair"
        assert result["errors"] == {"base": "key_pending"}

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "credentials"

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {CONF_HOST: HOST, CONF_PASSWORD: PASSWORD}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    subentry = entry.get_subentries_of_type(SUBENTRY_TYPE_ENERGY_SITE)[0]
    assert subentry.data[CONF_HOST] == HOST


@pytest.mark.usefixtures("mock_rsa_key")
async def test_subentry_null_body_aborts_as_lookup_failure(hass: HomeAssistant) -> None:
    """A malformed authorized-clients read aborts rather than registering."""
    entry = await _setup_account_no_subentry(hass)

    with (
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.find_authorized_clients",
            new=AsyncMock(side_effect=InvalidResponse),
        ),
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.add_authorized_client",
            new=AsyncMock(),
        ) as mock_add,
    ):
        result = await _start_add_flow_select_site(hass, entry)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
    mock_add.assert_not_awaited()


@pytest.mark.usefixtures("mock_rsa_key")
@pytest.mark.parametrize(
    ("client_kwargs", "expected_error"),
    [
        pytest.param(
            {"connect_error": PowerwallAuthenticationError()},
            "invalid_password",
            id="wrong_gateway_password",
        ),
        pytest.param(
            {"connect_error": PowerwallConnectionError()},
            "cannot_connect",
            id="gateway_unreachable",
        ),
        pytest.param(
            {"status_error": PowerwallAuthenticationError()},
            "key_not_approved",
            id="signed_read_rejects_unapproved_key",
        ),
        pytest.param(
            {"status_error": PowerwallFaultError("MESSAGEFAULT_ERROR_BUSY")},
            "cannot_connect",
            id="signed_read_generic_gateway_fault",
        ),
        pytest.param(
            {"status_error": PowerwallConnectionError()},
            "cannot_connect",
            id="signed_read_unreachable",
        ),
    ],
)
async def test_subentry_credentials_errors(
    hass: HomeAssistant,
    client_kwargs: dict[str, Exception],
    expected_error: str,
) -> None:
    """The credentials step reports each local verification failure distinctly."""
    entry = await _setup_account_no_subentry(hass)

    client = _mock_powerwall_client(**client_kwargs)
    with (
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.find_authorized_clients",
            new=AsyncMock(
                return_value=_own_key_clients(AuthorizedClientState.VERIFIED)
            ),
        ),
        patch(
            "homeassistant.components.teslemetry.config_flow.PowerwallClient",
            return_value=client,
        ),
    ):
        result = await _start_add_flow_select_site(hass, entry)
        assert result["step_id"] == "credentials"

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {CONF_HOST: HOST, CONF_PASSWORD: PASSWORD}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "credentials"
    assert result["errors"] == {"base": expected_error}
    assert not entry.get_subentries_of_type(SUBENTRY_TYPE_ENERGY_SITE)


def _credentials_host_default(result: SubentryFlowResult) -> str:
    """Return the CONF_HOST field's schema default from a credentials form result."""
    for key in result["data_schema"].schema:
        if key == CONF_HOST:
            return key.default()
    raise AssertionError("CONF_HOST field not found in credentials schema")


@pytest.mark.usefixtures("mock_rsa_key")
async def test_subentry_credentials_prefills_discovered_host(
    hass: HomeAssistant,
) -> None:
    """A discovered gateway address pre-fills the credentials CONF_HOST default."""
    entry = await _setup_account_no_subentry(hass)
    discovered_host = "192.168.1.138"

    with (
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.find_gateway_address",
            new=AsyncMock(return_value=discovered_host),
        ),
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.find_authorized_clients",
            new=AsyncMock(
                return_value=_own_key_clients(AuthorizedClientState.VERIFIED)
            ),
        ),
    ):
        result = await _start_add_flow_select_site(hass, entry)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "credentials"
    assert _credentials_host_default(result) == discovered_host


async def _setup_account_no_subentry(hass: HomeAssistant) -> MockConfigEntry:
    """Set up an account entry with no local-control subentry (nothing opted in)."""
    entry = mock_config_entry()
    entry.add_to_hass(hass)
    with patch("homeassistant.components.teslemetry.PLATFORMS", []):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


async def test_no_subentry_created_at_setup(hass: HomeAssistant) -> None:
    """Setup never auto-creates a local-control subentry; it is opt-in."""
    entry = await _setup_account_no_subentry(hass)

    assert not entry.get_subentries_of_type(SUBENTRY_TYPE_ENERGY_SITE)
    energysite = entry.runtime_data.energysites[0]
    assert energysite.can_local_control
    assert energysite.subentry_id is None
    assert not isinstance(energysite.api, EnergySiteRouter)


@pytest.mark.usefixtures("mock_rsa_key")
async def test_add_flow_lists_only_not_added_sites(hass: HomeAssistant) -> None:
    """The add flow offers battery sites that have not already been added."""
    entry = await _setup_account_no_subentry(hass)

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_ENERGY_SITE),
        context={"source": "user"},
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "user"
    schema = result["data_schema"].schema
    site_field = next(iter(schema))
    assert site_field == CONF_SITE_ID
    # Only the battery-capable site is selectable; the componentless site is not.
    assert set(schema[site_field].container) == {str(SITE_ID)}


@pytest.mark.usefixtures("mock_rsa_key")
async def test_add_flow_aborts_when_all_sites_added(hass: HomeAssistant) -> None:
    """The add flow aborts when every battery site is already added."""
    entry = _entry_with_unpaired_subentry()
    entry.add_to_hass(hass)
    with patch("homeassistant.components.teslemetry.PLATFORMS", []):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_ENERGY_SITE),
        context={"source": "user"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "no_energy_sites"


@pytest.mark.usefixtures("mock_rsa_key")
async def test_add_flow_creates_subentry_bound_to_existing_device(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
) -> None:
    """The add flow creates a subentry for the site and reuses its device."""
    entry = await _setup_account_no_subentry(hass)
    devices_before = dr.async_entries_for_config_entry(device_registry, entry.entry_id)
    site_device = next(
        device
        for device in devices_before
        if (DOMAIN, str(SITE_ID)) in device.identifiers
    )

    client = _mock_powerwall_client()
    with (
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.find_authorized_clients",
            new=AsyncMock(
                return_value=_own_key_clients(AuthorizedClientState.VERIFIED)
            ),
        ),
        patch(
            "homeassistant.components.teslemetry.config_flow.PowerwallClient",
            return_value=client,
        ),
        patch.object(hass.config_entries, "async_schedule_reload"),
    ):
        result = await hass.config_entries.subentries.async_init(
            (entry.entry_id, SUBENTRY_TYPE_ENERGY_SITE),
            context={"source": "user"},
        )
        assert result["step_id"] == "user"

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {CONF_SITE_ID: str(SITE_ID)}
        )
        assert result["step_id"] == "credentials"

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {CONF_HOST: HOST, CONF_PASSWORD: PASSWORD}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    subentry = entry.get_subentries_of_type(SUBENTRY_TYPE_ENERGY_SITE)[0]
    assert subentry.unique_id == str(SITE_ID)
    assert subentry.data[CONF_SITE_ID] == SITE_ID
    assert subentry.data[CONF_HOST] == HOST
    assert subentry.data[CONF_PASSWORD] == PASSWORD

    # No duplicate device: the same site device is reused.
    site_devices = [
        device
        for device in dr.async_entries_for_config_entry(device_registry, entry.entry_id)
        if (DOMAIN, str(SITE_ID)) in device.identifiers
    ]
    assert [device.id for device in site_devices] == [site_device.id]


async def test_get_rsa_key_pem_generates_and_caches(hass: HomeAssistant) -> None:
    """The RSA key is generated/read once, then served from the hass.data cache."""
    with (
        patch(
            "homeassistant.components.teslemetry.Teslemetry.get_rsa_private_key",
            new=AsyncMock(),
        ) as mock_get_key,
        patch(
            "homeassistant.components.teslemetry.Path.read_bytes",
            return_value=_TEST_RSA_KEY_PEM,
        ),
    ):
        first = await _async_get_rsa_key_pem(hass)
        second = await _async_get_rsa_key_pem(hass)

    assert first == _TEST_RSA_KEY_PEM
    assert second == _TEST_RSA_KEY_PEM
    mock_get_key.assert_awaited_once()


@pytest.mark.parametrize(
    ("local_error", "expected", "cloud_awaits"),
    [
        pytest.param(None, {"routed": "local"}, 0, id="local_success"),
        pytest.param(
            PowerwallError("boom"), {"routed": "cloud"}, 1, id="cloud_fallback"
        ),
    ],
)
async def test_energy_site_router_command_routing(
    hass: HomeAssistant,
    local_error: Exception | None,
    expected: dict[str, str],
    cloud_awaits: int,
) -> None:
    """A command routes to the local Powerwall first and falls back to cloud."""
    entry = _entry_with_powerwall()
    entry.add_to_hass(hass)

    with (
        patch(
            "homeassistant.components.teslemetry._async_get_rsa_key_pem",
            return_value=_TEST_RSA_KEY_PEM,
        ),
        patch("homeassistant.components.teslemetry.PLATFORMS", []),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    router = entry.runtime_data.energysites[0].api
    assert isinstance(router, EnergySiteRouter)

    local = AsyncMock(side_effect=local_error, return_value={"routed": "local"})
    cloud = AsyncMock(return_value={"routed": "cloud"})
    with (
        patch("aiopowerwall.energysite.PowerwallEnergySite.backup", new=local),
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.backup",
            new=cloud,
        ),
    ):
        result = await router.backup(50)

    assert result == expected
    local.assert_awaited_once_with(50)
    assert cloud.await_count == cloud_awaits


async def test_stale_cleanup_preserves_foreign_subentry(hass: HomeAssistant) -> None:
    """Energy stale-subentry cleanup does not remove other subentry types."""
    entry = mock_config_entry()
    entry.add_to_hass(hass)
    foreign = ConfigSubentry(
        data=MappingProxyType({"vin": "VIN123"}),
        subentry_type="vehicle",
        title="A Vehicle",
        unique_id="VIN123",
    )
    hass.config_entries.async_add_subentry(entry, foreign)

    with patch("homeassistant.components.teslemetry.PLATFORMS", []):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert foreign.subentry_id in entry.subentries
    assert entry.subentries[foreign.subentry_id].subentry_type == "vehicle"


async def test_stale_cleanup_removes_energy_subentry(hass: HomeAssistant) -> None:
    """A paired site that is gone from the account has its subentry pruned."""
    entry = _entry_with_powerwall()
    entry.add_to_hass(hass)
    subentry_id = entry.get_subentries_of_type(SUBENTRY_TYPE_ENERGY_SITE)[0].subentry_id

    products = deepcopy(PRODUCTS)
    products["response"] = [
        product
        for product in products["response"]
        if product.get("energy_site_id") != SITE_ID
    ]

    with (
        patch("tesla_fleet_api.teslemetry.Teslemetry.products", return_value=products),
        patch("homeassistant.components.teslemetry.PLATFORMS", []),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert subentry_id not in entry.subentries


async def test_stale_cleanup_preserves_pairing_on_transient_access_loss(
    hass: HomeAssistant,
) -> None:
    """A paired site that momentarily reports no access keeps its subentry."""
    entry = _entry_with_powerwall()
    entry.add_to_hass(hass)
    subentry_id = entry.get_subentries_of_type(SUBENTRY_TYPE_ENERGY_SITE)[0].subentry_id

    metadata = deepcopy(METADATA)
    metadata["energy_sites"][str(SITE_ID)]["access"] = False

    with (
        patch("tesla_fleet_api.teslemetry.Teslemetry.metadata", return_value=metadata),
        patch("homeassistant.components.teslemetry.PLATFORMS", []),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert subentry_id in entry.subentries
    assert entry.subentries[subentry_id].data[CONF_HOST] == HOST
    assert entry.subentries[subentry_id].data[CONF_PASSWORD] == PASSWORD


async def test_solar_only_site_has_no_local_control(hass: HomeAssistant) -> None:
    """A solar-only site gets no local-control subentry: there is no Powerwall."""
    products = deepcopy(PRODUCTS)
    site = next(
        product
        for product in products["response"]
        if product.get("energy_site_id") == SITE_ID
    )
    site["components"]["battery"] = False
    site["components"].pop("wall_connectors")

    entry = mock_config_entry()
    entry.add_to_hass(hass)
    with (
        patch("tesla_fleet_api.teslemetry.Teslemetry.products", return_value=products),
        patch("homeassistant.components.teslemetry.PLATFORMS", []),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert not entry.get_subentries_of_type(SUBENTRY_TYPE_ENERGY_SITE)
    energysite = entry.runtime_data.energysites[0]
    assert energysite.subentry_id is None
    assert not isinstance(energysite.api, EnergySiteRouter)


async def test_stale_cleanup_preserves_pairing_without_energy_scope(
    hass: HomeAssistant,
) -> None:
    """Losing the energy scope must not delete a paired site's stored credentials."""
    entry = _entry_with_powerwall()
    entry.add_to_hass(hass)
    subentry_id = entry.get_subentries_of_type(SUBENTRY_TYPE_ENERGY_SITE)[0].subentry_id

    with (
        patch(
            "tesla_fleet_api.teslemetry.Teslemetry.metadata",
            return_value=METADATA_NOSCOPE,
        ),
        patch("homeassistant.components.teslemetry.PLATFORMS", []),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert not entry.runtime_data.energysites
    assert subentry_id in entry.subentries
    assert entry.subentries[subentry_id].data[CONF_HOST] == HOST
    assert entry.subentries[subentry_id].data[CONF_PASSWORD] == PASSWORD


@pytest.mark.usefixtures("mock_rsa_key")
async def test_subentry_credentials_password_truncated(hass: HomeAssistant) -> None:
    """A full Wi-Fi password is trimmed to its final five characters."""
    entry = await _setup_account_no_subentry(hass)

    client = _mock_powerwall_client()
    with (
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.find_authorized_clients",
            new=AsyncMock(
                return_value=_own_key_clients(AuthorizedClientState.VERIFIED)
            ),
        ),
        patch(
            "homeassistant.components.teslemetry.config_flow.PowerwallClient",
            return_value=client,
        ) as mock_client,
        patch.object(hass.config_entries, "async_schedule_reload"),
    ):
        result = await _start_add_flow_select_site(hass, entry)
        assert result["step_id"] == "credentials"

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {CONF_HOST: HOST, CONF_PASSWORD: "long-wifi-password"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.CREATE_ENTRY
    subentry = entry.get_subentries_of_type(SUBENTRY_TYPE_ENERGY_SITE)[0]
    assert subentry.data[CONF_PASSWORD] == "sword"
    assert mock_client.call_args.kwargs["gateway_password"] == "sword"


@pytest.mark.usefixtures("mock_rsa_key")
async def test_wall_connector_only_site_not_offered_for_local_control(
    hass: HomeAssistant,
) -> None:
    """A wall-connector-only site can't do local control; only a Powerwall can."""
    products = deepcopy(PRODUCTS)
    products["response"].append(
        {
            "energy_site_id": WALL_CONNECTOR_SITE_ID,
            "site_name": "Wall Connector Site",
            "components": {
                "battery": False,
                "solar": False,
                "grid": True,
                "wall_connectors": [{"device_id": "wc-1", "din": "WC-DIN-1"}],
            },
        }
    )
    metadata = deepcopy(METADATA)
    metadata["energy_sites"][str(WALL_CONNECTOR_SITE_ID)] = {
        "access": True,
        "name": "Wall Connector Site",
    }

    entry = mock_config_entry()
    entry.add_to_hass(hass)
    with (
        patch("tesla_fleet_api.teslemetry.Teslemetry.products", return_value=products),
        patch("tesla_fleet_api.teslemetry.Teslemetry.metadata", return_value=metadata),
        patch("homeassistant.components.teslemetry.PLATFORMS", []),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    assert not entry.get_subentries_of_type(SUBENTRY_TYPE_ENERGY_SITE)

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_ENERGY_SITE),
        context={"source": "user"},
    )
    schema = result["data_schema"].schema
    site_field = next(iter(schema))
    assert set(schema[site_field].container) == {str(SITE_ID)}


async def test_add_flow_aborts_when_entry_not_loaded(hass: HomeAssistant) -> None:
    """The add flow aborts when the account entry is not loaded."""
    entry = mock_config_entry()
    entry.add_to_hass(hass)

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_ENERGY_SITE),
        context={"source": "user"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "entry_not_loaded"


@pytest.mark.usefixtures("mock_rsa_key")
async def test_gateway_discovery_failure_proceeds_without_host(
    hass: HomeAssistant,
) -> None:
    """A failed gateway-address discovery leaves the host default unset."""
    entry = await _setup_account_no_subentry(hass)

    with (
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.find_gateway_address",
            new=AsyncMock(side_effect=ClientError),
        ),
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.find_authorized_clients",
            new=AsyncMock(
                return_value=_own_key_clients(AuthorizedClientState.VERIFIED)
            ),
        ),
    ):
        result = await _start_add_flow_select_site(hass, entry)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "credentials"
    assert _credentials_host_default(result) == DEFAULT_GATEWAY_HOST


@pytest.mark.usefixtures("mock_rsa_key")
async def test_pending_key_resumes_without_reregister(hass: HomeAssistant) -> None:
    """A key already pending on the gateway resumes pairing without re-adding it."""
    entry = await _setup_account_no_subentry(hass)

    with (
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.find_authorized_clients",
            new=AsyncMock(
                return_value=_own_key_clients(
                    AuthorizedClientState.PENDING_VERIFICATION
                )
            ),
        ),
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.add_authorized_client",
            new=AsyncMock(),
        ) as mock_add,
    ):
        result = await _start_add_flow_select_site(hass, entry)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pair"
    mock_add.assert_not_awaited()


@pytest.mark.usefixtures("mock_rsa_key")
async def test_unrecognized_state_aborts_pairing(hass: HomeAssistant) -> None:
    """An unrecognized authorized-client state aborts rather than re-registering."""
    entry = await _setup_account_no_subentry(hass)

    with (
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.find_authorized_clients",
            new=AsyncMock(return_value=_own_key_clients("gremlin")),
        ),
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.add_authorized_client",
            new=AsyncMock(),
        ) as mock_add,
    ):
        result = await _start_add_flow_select_site(hass, entry)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
    mock_add.assert_not_awaited()


@pytest.mark.usefixtures("mock_rsa_key")
async def test_add_authorized_client_failure_aborts(hass: HomeAssistant) -> None:
    """A failure while registering the key aborts the flow."""
    entry = await _setup_account_no_subentry(hass)

    with (
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.find_authorized_clients",
            new=AsyncMock(return_value=_empty_clients()),
        ),
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.add_authorized_client",
            new=AsyncMock(side_effect=ClientError),
        ),
    ):
        result = await _start_add_flow_select_site(hass, entry)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


@pytest.mark.usefixtures("mock_rsa_key")
@pytest.mark.parametrize(
    ("second_lookup", "expected_error"),
    [
        pytest.param(InvalidResponse(), "cannot_connect", id="lookup_failure"),
        pytest.param(_empty_clients(), "key_not_registered", id="key_not_registered"),
        pytest.param(_own_key_clients("gremlin"), "cannot_connect", id="unknown_state"),
    ],
)
async def test_pair_step_second_lookup_errors(
    hass: HomeAssistant,
    second_lookup: Exception | AuthorizedClients,
    expected_error: str,
) -> None:
    """Re-checking the pending key reports each non-approval outcome on the form."""
    entry = await _setup_account_no_subentry(hass)

    with (
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.find_authorized_clients",
            new=AsyncMock(side_effect=[_empty_clients(), second_lookup]),
        ),
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.add_authorized_client",
            new=AsyncMock(),
        ),
    ):
        result = await _start_add_flow_select_site(hass, entry)
        assert result["step_id"] == "pair"

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pair"
    assert result["errors"] == {"base": expected_error}
