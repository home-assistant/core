"""Test the Teslemetry energy site local Powerwall routing and pairing flow."""

from collections.abc import Generator
from copy import deepcopy
from types import MappingProxyType
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from aiopowerwall import (
    PowerwallAuthenticationError,
    PowerwallConnectionError,
    PowerwallError,
)
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import pytest
from tesla_fleet_api.const import AuthorizedClientState
from tesla_fleet_api.exceptions import TeslaFleetError
from tesla_fleet_api.tesla import EnergySiteRouter
from tesla_fleet_api.teslemetry import EnergySite

from homeassistant.components.teslemetry import _async_get_rsa_key_pem
from homeassistant.components.teslemetry.const import (
    CONF_SITE_ID,
    SUBENTRY_TYPE_ENERGY_SITE,
)
from homeassistant.config_entries import ConfigSubentry, ConfigSubentryData
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.core import HomeAssistant
from homeassistant.data_entry_flow import FlowResultType

from . import mock_config_entry
from .const import METADATA, PRODUCTS

from tests.common import MockConfigEntry

SITE_ID = 123456
WALL_CONNECTOR_SITE_ID = 555555
HOST = "192.168.91.1"
PASSWORD = "abcde"
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


def _mock_powerwall_client(*, connect_error: Exception | None = None) -> MagicMock:
    """Return a mock aiopowerwall PowerwallClient async context manager."""
    client = MagicMock()
    client.__aenter__ = AsyncMock(return_value=client)
    client.__aexit__ = AsyncMock(return_value=False)
    client.connect = AsyncMock(side_effect=connect_error)
    return client


def _verified_clients_response() -> dict:
    """Return a list_authorized_clients response verifying our public key.

    Includes a non-dict entry and a mismatched key so the library's typed
    ``find_authorized_clients`` accessor has noise to skip past.
    """
    return {
        "response": {
            "authorized_clients": [
                "not-a-dict",
                {"public_key": "some-other-key", "state": 3},
                {"public_key": PUBLIC_KEY_B64, "state": 3},
            ]
        }
    }


def _unverified_clients_response() -> dict:
    """Return a list_authorized_clients response with no matching client."""
    return {"response": {"authorized_clients": [{"public_key": "other", "state": 1}]}}


def _pending_clients_response() -> dict:
    """Return a list_authorized_clients response with our key still pending."""
    return {
        "response": {"authorized_clients": [{"public_key": PUBLIC_KEY_B64, "state": 1}]}
    }


def _empty_clients_response() -> dict:
    """Return a response whose authorized-clients list is explicitly empty."""
    return {"response": {"authorized_clients": []}}


def _real_shape_clients_response(state: AuthorizedClientState) -> dict:
    """Return a response matching the gateway's real envelope and field shape.

    Modeled on a live ``authorized_clients`` capture: the list is nested under
    ``clients`` (not ``authorized_clients``), and each entry carries the full
    real field set including an object-shaped ``added_time``. Includes a
    decoy entry so the flow's key-matching predicate has noise to skip past.
    """
    return {
        "response": {
            "request_id": "03153d0c37283795cf0d1a593eebd9a0",
            "clients": [
                {
                    "type": 1,
                    "description": "Some Other App",
                    "key_type": 1,
                    "public_key": "not-a-match",
                    "roles": [1],
                    "state": 3,
                    "verification": 1,
                    "added_time": {"seconds": 1700000000},
                },
                {
                    "type": 1,
                    "description": "Home Assistant",
                    "key_type": 1,
                    "public_key": PUBLIC_KEY_B64,
                    "roles": [1],
                    "state": int(state),
                    "verification": 1,
                    "added_time": {"seconds": 1783997627},
                },
            ],
        }
    }


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


async def _setup_energy_site_subentry(hass: HomeAssistant) -> MockConfigEntry:
    """Set up an entry and return it with an (unpaired) energy site subentry."""
    entry = mock_config_entry()
    entry.add_to_hass(hass)
    with patch("homeassistant.components.teslemetry.PLATFORMS", []):
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
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.list_authorized_clients",
            new=AsyncMock(return_value=_verified_clients_response()),
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


@pytest.mark.usefixtures("mock_rsa_key")
async def test_subentry_pairing_requires_key_approval(hass: HomeAssistant) -> None:
    """Pairing registers the key, then advances to credentials once approved."""
    entry = await _setup_energy_site_subentry(hass)
    subentry_id = entry.get_subentries_of_type(SUBENTRY_TYPE_ENERGY_SITE)[0].subentry_id

    client = _mock_powerwall_client()
    with (
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.list_authorized_clients",
            new=AsyncMock(
                side_effect=[
                    _empty_clients_response(),
                    _pending_clients_response(),
                    _verified_clients_response(),
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
        # reconfigure -> key absent -> add_authorized_client -> pair
        result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "pair"
        mock_add.assert_awaited_once()

        # confirm pair while still pending -> re-shows pair with an error
        result = await hass.config_entries.subentries.async_configure(
            result["flow_id"], {}
        )
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "pair"
        assert result["errors"] == {"base": "key_pending"}

        # confirm pair again, now verified -> credentials
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
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.list_authorized_clients",
            new=AsyncMock(return_value=_empty_clients_response()),
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
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.list_authorized_clients",
            new=AsyncMock(
                return_value=_real_shape_clients_response(
                    AuthorizedClientState.VERIFIED
                )
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
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.list_authorized_clients",
            new=AsyncMock(return_value=_real_shape_clients_response(state)),
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
    """A bare null (200) authorized-clients body aborts rather than registering.

    Tesla's undocumented endpoint can answer with JSON ``null``; the library's
    typed accessor now raises ``InvalidResponse`` for it rather than collapsing
    it to an empty client list, since a malformed response could just as
    easily be hiding an already-registered key. The flow must not mistake this
    for an absent key and re-register it.
    """
    entry = await _setup_energy_site_subentry(hass)
    subentry_id = entry.get_subentries_of_type(SUBENTRY_TYPE_ENERGY_SITE)[0].subentry_id

    with (
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.list_authorized_clients",
            new=AsyncMock(return_value=None),
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
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.list_authorized_clients",
            new=AsyncMock(return_value=_unverified_clients_response()),
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
async def test_subentry_credentials_invalid_password(hass: HomeAssistant) -> None:
    """The credentials step shows an error when the gateway password is wrong."""
    entry = await _setup_energy_site_subentry(hass)
    subentry_id = entry.get_subentries_of_type(SUBENTRY_TYPE_ENERGY_SITE)[0].subentry_id

    client = _mock_powerwall_client(connect_error=PowerwallAuthenticationError())
    with (
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.list_authorized_clients",
            new=AsyncMock(return_value=_verified_clients_response()),
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
    assert result["errors"] == {"base": "invalid_password"}


@pytest.mark.usefixtures("mock_rsa_key")
async def test_subentry_credentials_cannot_connect(hass: HomeAssistant) -> None:
    """The credentials step shows an error when the gateway is unreachable."""
    entry = await _setup_energy_site_subentry(hass)
    subentry_id = entry.get_subentries_of_type(SUBENTRY_TYPE_ENERGY_SITE)[0].subentry_id

    client = _mock_powerwall_client(connect_error=PowerwallConnectionError())
    with (
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.list_authorized_clients",
            new=AsyncMock(return_value=_verified_clients_response()),
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
    assert result["errors"] == {"base": "cannot_connect"}


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
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.list_authorized_clients",
            new=AsyncMock(return_value=_verified_clients_response()),
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
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.list_authorized_clients",
            new=AsyncMock(return_value=_verified_clients_response()),
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
