"""Test the Teslemetry energy site local Powerwall routing and pairing flow."""

from collections.abc import Generator
from copy import deepcopy
from types import MappingProxyType
from typing import Any
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from aiohttp import ClientResponseError, RequestInfo
from aiopowerwall import (
    DEFAULT_GATEWAY_HOST,
    PowerwallAuthenticationError,
    PowerwallConnectionError,
    PowerwallError,
    PowerwallFaultError,
)
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from multidict import CIMultiDict
import pytest
from tesla_fleet_api.const import AuthorizedClientState
from tesla_fleet_api.exceptions import InvalidResponse, TeslaFleetError
from tesla_fleet_api.tesla import EnergySiteRouter
from tesla_fleet_api.teslemetry import EnergySite
from tesla_fleet_api.teslemetry.energysite import AuthorizedClient, AuthorizedClients
from yarl import URL

from homeassistant.components.teslemetry import _async_get_rsa_key_pem
from homeassistant.components.teslemetry.const import (
    CONF_SITE_ID,
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
    """Default gateway-address discovery to no result.

    Keeps every existing subentry test path deterministic now that
    ``async_step_reconfigure`` calls ``find_gateway_address``. Tests exercising
    discovery itself override this per-test.
    """
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
    """Return a typed client list carrying our key in the given state.

    Includes a decoy entry so the flow's own key-matching predicate has noise
    to skip past. Unwrapping the gateway's raw envelope into these typed
    entries is the library's job, so tests drive the accessor the integration
    actually calls rather than the raw command underneath it.
    """
    return AuthorizedClients(
        clients=[
            AuthorizedClient(
                public_key="some-other-key",
                state=AuthorizedClientState.VERIFIED,
                raw={},
            ),
            AuthorizedClient(public_key=PUBLIC_KEY_B64, state=state, raw={}),
        ],
        raw=None,
    )


def _unverified_clients() -> AuthorizedClients:
    """Return a typed client list holding no entry for our key."""
    return AuthorizedClients(
        clients=[
            AuthorizedClient(
                public_key="other", state=AuthorizedClientState.PENDING, raw={}
            )
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


async def _setup_energy_site_subentry(
    hass: HomeAssistant, products: dict[str, Any] | None = None
) -> MockConfigEntry:
    """Set up an entry and return it with an (unpaired) energy site subentry."""
    entry = mock_config_entry()
    entry.add_to_hass(hass)
    with (
        patch(
            "tesla_fleet_api.teslemetry.Teslemetry.products",
            return_value=products or PRODUCTS,
        ),
        patch("homeassistant.components.teslemetry.PLATFORMS", []),
    ):
        await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    return entry


@pytest.mark.usefixtures("mock_rsa_key")
async def test_subentry_pairing_already_verified(hass: HomeAssistant) -> None:
    """Pairing skips straight to credentials when the key is already verified."""
    entry = await _setup_energy_site_subentry(hass)
    subentry_id = entry.get_subentries_of_type(SUBENTRY_TYPE_ENERGY_SITE)[0].subentry_id

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
        patch.object(hass.config_entries, "async_schedule_reload") as mock_reload,
    ):
        result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "credentials"

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {CONF_HOST: HOST, CONF_PASSWORD: PASSWORD}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.subentries[subentry_id].data[CONF_HOST] == HOST
    assert entry.subentries[subentry_id].data[CONF_PASSWORD] == PASSWORD
    mock_reload.assert_called_once_with(entry.entry_id)
    client.connect.assert_awaited_once()
    client.get_status.assert_awaited_once()


@pytest.mark.usefixtures("mock_rsa_key")
async def test_subentry_pairing_requires_key_approval(hass: HomeAssistant) -> None:
    """Pairing registers the key, then advances to credentials once approved."""
    entry = await _setup_energy_site_subentry(hass)
    subentry_id = entry.get_subentries_of_type(SUBENTRY_TYPE_ENERGY_SITE)[0].subentry_id

    client = _mock_powerwall_client()
    with (
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.find_authorized_clients",
            new=AsyncMock(
                side_effect=[
                    _empty_clients(),
                    _own_key_clients(AuthorizedClientState.PENDING),
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
        result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
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

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.subentries[subentry_id].data[CONF_HOST] == HOST


@pytest.mark.usefixtures("mock_rsa_key")
async def test_subentry_pair_key_not_registered(hass: HomeAssistant) -> None:
    """The pair step errors clearly if the key is not found on the gateway."""
    entry = await _setup_energy_site_subentry(hass)
    subentry_id = entry.get_subentries_of_type(SUBENTRY_TYPE_ENERGY_SITE)[0].subentry_id

    with (
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.find_authorized_clients",
            new=AsyncMock(return_value=_empty_clients()),
        ),
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.add_authorized_client",
            new=AsyncMock(),
        ),
    ):
        result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
        assert result["step_id"] == "pair"

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pair"
    assert result["errors"] == {"base": "key_not_registered"}


@pytest.mark.usefixtures("mock_rsa_key")
async def test_subentry_recognizes_own_verified_key_no_reregister(
    hass: HomeAssistant,
) -> None:
    """A real gateway response recognizes our own VERIFIED key and skips re-adding it."""
    entry = await _setup_energy_site_subentry(hass)
    subentry_id = entry.get_subentries_of_type(SUBENTRY_TYPE_ENERGY_SITE)[0].subentry_id

    client = _mock_powerwall_client()
    add_client = AsyncMock()
    with (
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.find_authorized_clients",
            new=AsyncMock(
                return_value=_own_key_clients(AuthorizedClientState.VERIFIED)
            ),
        ),
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.add_authorized_client",
            new=add_client,
        ),
        patch(
            "homeassistant.components.teslemetry.config_flow.PowerwallClient",
            return_value=client,
        ),
        patch.object(hass.config_entries, "async_schedule_reload"),
    ):
        result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "credentials"
    add_client.assert_not_awaited()


@pytest.mark.usefixtures("mock_rsa_key")
@pytest.mark.parametrize(
    ("state", "expected_error"),
    [
        pytest.param(AuthorizedClientState.PENDING, "key_pending", id="pending"),
        pytest.param(
            AuthorizedClientState.PENDING_VERIFICATION,
            "key_pending_verification",
            id="pending_verification",
        ),
    ],
)
async def test_subentry_recognizes_own_pending_key_no_reregister(
    hass: HomeAssistant,
    state: AuthorizedClientState,
    expected_error: str,
) -> None:
    """A real gateway response recognizes our own pending key and skips re-adding it."""
    entry = await _setup_energy_site_subentry(hass)
    subentry_id = entry.get_subentries_of_type(SUBENTRY_TYPE_ENERGY_SITE)[0].subentry_id

    add_client = AsyncMock()
    with (
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.find_authorized_clients",
            new=AsyncMock(return_value=_own_key_clients(state)),
        ),
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.add_authorized_client",
            new=add_client,
        ),
    ):
        result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "pair"
        assert not result["errors"]

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "pair"
    assert result["errors"] == {"base": expected_error}
    add_client.assert_not_awaited()


@pytest.mark.usefixtures("mock_rsa_key")
async def test_subentry_null_body_aborts_as_lookup_failure(hass: HomeAssistant) -> None:
    """A malformed authorized-clients read aborts rather than registering.

    Tesla's undocumented endpoint can answer with JSON ``null``; the library's
    typed accessor raises ``InvalidResponse`` for it rather than collapsing it
    to an empty client list, since a malformed response could just as easily be
    hiding an already-registered key. The flow must not mistake that failure
    for an absent key and re-register it.
    """
    entry = await _setup_energy_site_subentry(hass)
    subentry_id = entry.get_subentries_of_type(SUBENTRY_TYPE_ENERGY_SITE)[0].subentry_id

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
        result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"
    mock_add.assert_not_awaited()


@pytest.mark.usefixtures("mock_rsa_key")
async def test_subentry_add_authorized_client_fails(hass: HomeAssistant) -> None:
    """Reconfigure aborts if registering the key with the gateway fails."""
    entry = await _setup_energy_site_subentry(hass)
    subentry_id = entry.get_subentries_of_type(SUBENTRY_TYPE_ENERGY_SITE)[0].subentry_id

    with (
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.find_authorized_clients",
            new=AsyncMock(return_value=_unverified_clients()),
        ),
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.add_authorized_client",
            new=AsyncMock(side_effect=TeslaFleetError()),
        ),
    ):
        result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


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
    """The credentials step reports each local verification failure distinctly.

    A key the gateway has not approved only fails the signed read, so it must
    not be reported as a bad password. A generic gateway fault (busy, timeout,
    internal) is a different failure than a rejected key and must not be
    reported as one.
    """
    entry = await _setup_energy_site_subentry(hass)
    subentry_id = entry.get_subentries_of_type(SUBENTRY_TYPE_ENERGY_SITE)[0].subentry_id

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
        result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
        assert result["step_id"] == "credentials"

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {CONF_HOST: HOST, CONF_PASSWORD: PASSWORD}
        )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "credentials"
    assert result["errors"] == {"base": expected_error}
    assert CONF_HOST not in entry.subentries[subentry_id].data


@pytest.mark.usefixtures("mock_rsa_key")
@pytest.mark.parametrize(
    "din",
    [
        pytest.param("SOMEONE-ELSES-GATEWAY", id="different_gateway"),
        pytest.param("", id="no_din_reported"),
    ],
)
async def test_subentry_credentials_gateway_mismatch(
    hass: HomeAssistant, din: str
) -> None:
    """Pairing aborts when the local gateway is not the site's own gateway.

    The RSA key authorizes every gateway on the account, so without this the
    subentry would command another site's house. The mismatch is caught
    before the signed read, so a gateway that isn't ours is never sent one.
    """
    entry = await _setup_energy_site_subentry(hass)
    subentry_id = entry.get_subentries_of_type(SUBENTRY_TYPE_ENERGY_SITE)[0].subentry_id

    client = _mock_powerwall_client(din=din)
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
        result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
        assert result["step_id"] == "credentials"

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {CONF_HOST: HOST, CONF_PASSWORD: PASSWORD}
        )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "gateway_mismatch"
    assert result["description_placeholders"] == {
        "expected": GATEWAY_DIN,
        "actual": din,
    }
    assert CONF_HOST not in entry.subentries[subentry_id].data
    client.get_status.assert_not_awaited()


@pytest.mark.usefixtures("mock_rsa_key")
async def test_subentry_credentials_without_cloud_gateway_id(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """A site with no cloud gateway ID pairs, but says so rather than skipping quietly.

    There is nothing to compare the local DIN against, and refusing a valid
    gateway would be worse than not binding it.
    """
    products = deepcopy(PRODUCTS)
    site = next(
        product
        for product in products["response"]
        if product.get("energy_site_id") == SITE_ID
    )
    site.pop("gateway_id")

    entry = await _setup_energy_site_subentry(hass, products=products)
    subentry_id = entry.get_subentries_of_type(SUBENTRY_TYPE_ENERGY_SITE)[0].subentry_id

    client = _mock_powerwall_client(din="UNKNOWN-GATEWAY")
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
        result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
        assert result["step_id"] == "credentials"

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {CONF_HOST: HOST, CONF_PASSWORD: PASSWORD}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.subentries[subentry_id].data[CONF_HOST] == HOST
    assert f"Energy site {SITE_ID} reports no gateway ID" in caplog.text
    assert caplog.records[-1].levelname == "WARNING"


@pytest.mark.usefixtures("mock_rsa_key")
async def test_subentry_credentials_gateway_din_normalized(
    hass: HomeAssistant,
) -> None:
    """A case or whitespace skew in the local DIN still pairs the same gateway."""
    entry = await _setup_energy_site_subentry(hass)
    subentry_id = entry.get_subentries_of_type(SUBENTRY_TYPE_ENERGY_SITE)[0].subentry_id

    client = _mock_powerwall_client(din=f"  {GATEWAY_DIN.lower()} ")
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
        result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
        assert result["step_id"] == "credentials"

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {CONF_HOST: HOST, CONF_PASSWORD: PASSWORD}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reconfigure_successful"
    assert entry.subentries[subentry_id].data[CONF_HOST] == HOST


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
    entry = await _setup_energy_site_subentry(hass)
    subentry_id = entry.get_subentries_of_type(SUBENTRY_TYPE_ENERGY_SITE)[0].subentry_id
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
        result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "credentials"
    assert _credentials_host_default(result) == discovered_host


@pytest.mark.usefixtures("mock_rsa_key")
@pytest.mark.parametrize(
    "error",
    [
        pytest.param(TeslaFleetError(), id="tesla_fleet_error"),
        pytest.param(
            ClientResponseError(
                RequestInfo(URL("http://gateway"), "GET", CIMultiDict()), (), status=500
            ),
            id="client_response_error",
        ),
    ],
)
async def test_subentry_credentials_discovery_error_falls_back(
    hass: HomeAssistant,
    error: Exception,
) -> None:
    """Discovery is best-effort: any lookup error falls back to the default host.

    Both exception types escape the same cloud-command path, and neither may
    abort the flow - the user must still reach the credentials step.
    """
    entry = await _setup_energy_site_subentry(hass)
    subentry_id = entry.get_subentries_of_type(SUBENTRY_TYPE_ENERGY_SITE)[0].subentry_id

    with (
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.find_gateway_address",
            new=AsyncMock(side_effect=error),
        ),
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.find_authorized_clients",
            new=AsyncMock(
                return_value=_own_key_clients(AuthorizedClientState.VERIFIED)
            ),
        ),
    ):
        result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "credentials"
    assert _credentials_host_default(result) == DEFAULT_GATEWAY_HOST


@pytest.mark.usefixtures("mock_rsa_key")
async def test_subentry_credentials_discovery_none_falls_back(
    hass: HomeAssistant,
) -> None:
    """A None discovery result falls back to the default host, no abort."""
    entry = await _setup_energy_site_subentry(hass)
    subentry_id = entry.get_subentries_of_type(SUBENTRY_TYPE_ENERGY_SITE)[0].subentry_id

    with (
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.find_gateway_address",
            new=AsyncMock(return_value=None),
        ),
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.find_authorized_clients",
            new=AsyncMock(
                return_value=_own_key_clients(AuthorizedClientState.VERIFIED)
            ),
        ),
    ):
        result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "credentials"
    assert _credentials_host_default(result) == DEFAULT_GATEWAY_HOST


@pytest.mark.usefixtures("mock_rsa_key")
async def test_subentry_reconfigure_reuses_router_fallback(
    hass: HomeAssistant,
) -> None:
    """Reconfiguring an already-paired site pairs against the cloud fallback."""
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

    subentry_id = entry.get_subentries_of_type(SUBENTRY_TYPE_ENERGY_SITE)[0].subentry_id
    assert isinstance(entry.runtime_data.energysites[0].api, EnergySiteRouter)

    new_password = "fghij"
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
        result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
        assert result["step_id"] == "credentials"

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {CONF_HOST: HOST, CONF_PASSWORD: new_password}
        )

    assert result["type"] is FlowResultType.ABORT
    assert entry.subentries[subentry_id].data[CONF_PASSWORD] == new_password


async def test_subentry_reconfigure_no_matching_energy_site(
    hass: HomeAssistant,
) -> None:
    """Reconfiguring a stale subentry with no matching energy site aborts."""
    entry = await _setup_energy_site_subentry(hass)

    stale_subentry = ConfigSubentry(
        data=MappingProxyType({CONF_SITE_ID: 999999}),
        subentry_type=SUBENTRY_TYPE_ENERGY_SITE,
        title="Stale Site",
        unique_id="999999",
    )
    hass.config_entries.async_add_subentry(entry, stale_subentry)

    result = await entry.start_subentry_reconfigure_flow(
        hass, stale_subentry.subentry_id
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "cannot_connect"


async def test_subentry_user_step_rejected(hass: HomeAssistant) -> None:
    """Manually adding an energy site subentry is rejected."""
    entry = await _setup_energy_site_subentry(hass)

    result = await hass.config_entries.subentries.async_init(
        (entry.entry_id, SUBENTRY_TYPE_ENERGY_SITE),
        context={"source": "user"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "not_supported"


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
    """A paired site that is gone from the account has its subentry pruned.

    The counterpart to the scope guard: with an authoritative inventory in hand,
    pruning must still happen.
    """
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
    """Losing the energy scope must not delete a paired site's stored credentials.

    Without ``energy_device_data`` the product loop skips every energy site, so
    the resolved site list is empty for want of an inventory rather than because
    the sites are gone. Pruning against it would silently drop the user's local
    gateway host/password.
    """
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


async def test_subentry_reconfigure_entry_not_loaded(hass: HomeAssistant) -> None:
    """Reconfigure aborts cleanly when the parent entry is not loaded."""
    entry = _entry_with_powerwall()
    entry.add_to_hass(hass)
    # Added but never set up, so runtime_data is absent.
    subentry_id = entry.get_subentries_of_type(SUBENTRY_TYPE_ENERGY_SITE)[0].subentry_id

    result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "entry_not_loaded"


@pytest.mark.usefixtures("mock_rsa_key")
async def test_subentry_credentials_password_truncated(hass: HomeAssistant) -> None:
    """A full Wi-Fi password is trimmed to its final five characters."""
    entry = await _setup_energy_site_subentry(hass)
    subentry_id = entry.get_subentries_of_type(SUBENTRY_TYPE_ENERGY_SITE)[0].subentry_id

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
        result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
        assert result["step_id"] == "credentials"

        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {CONF_HOST: HOST, CONF_PASSWORD: "long-wifi-password"}
        )
        await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert entry.subentries[subentry_id].data[CONF_PASSWORD] == "sword"
    assert mock_client.call_args.kwargs["gateway_password"] == "sword"


async def test_wall_connector_only_site_has_no_local_control(
    hass: HomeAssistant,
) -> None:
    """A wall-connector-only site gets no local-control subentry, a Powerwall does."""
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

    unique_ids = {
        subentry.unique_id
        for subentry in entry.get_subentries_of_type(SUBENTRY_TYPE_ENERGY_SITE)
    }
    assert str(SITE_ID) in unique_ids
    assert str(WALL_CONNECTOR_SITE_ID) not in unique_ids
