"""Test the Teslemetry energy site local Powerwall routing and pairing flow."""

from collections.abc import Generator
from types import MappingProxyType
from unittest.mock import AsyncMock, MagicMock, PropertyMock, patch

from aiopowerwall import PowerwallAuthenticationError, PowerwallConnectionError
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa
import pytest
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

from tests.common import MockConfigEntry

SITE_ID = 123456
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

    Includes a non-dict entry and a mismatched key to exercise the parsing
    helpers' defensive branches.
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
    """Return a list_authorized_clients response with no matching client.

    Nests the client list under an unrecognized wrapper key to exercise the
    parsing helpers' generic (non-keyed) fallback search.
    """
    return {"result": [{"public_key": "some-other-key", "state": 1}]}


def _empty_clients_response() -> dict:
    """Return a response with no client list findable anywhere in it."""
    return {"foo": "bar"}


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
    """Pairing registers the key, waits for approval, then proceeds."""
    entry = await _setup_energy_site_subentry(hass)
    subentry_id = entry.get_subentries_of_type(SUBENTRY_TYPE_ENERGY_SITE)[0].subentry_id

    client = _mock_powerwall_client()
    with (
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.list_authorized_clients",
            new=AsyncMock(
                side_effect=[
                    TeslaFleetError(),
                    TeslaFleetError(),
                    _verified_clients_response(),
                ]
            ),
        ),
        patch(
            "tesla_fleet_api.teslemetry.energysite.TeslemetryEnergySite.add_authorized_client",
            new=AsyncMock(),
        ) as mock_add,
        patch(
            "homeassistant.components.teslemetry.config_flow.asyncio.sleep",
            new=AsyncMock(),
        ),
        patch(
            "homeassistant.components.teslemetry.config_flow.PowerwallClient",
            return_value=client,
        ),
        patch.object(hass.config_entries, "async_schedule_reload"),
    ):
        # reconfigure -> list_authorized_clients raises -> add_authorized_client -> pair
        result = await entry.start_subentry_reconfigure_flow(hass, subentry_id)
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "pair"
        mock_add.assert_awaited_once()

        # confirm pair -> poll (unverified, then verified) -> credentials
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
async def test_subentry_pair_timeout(hass: HomeAssistant) -> None:
    """The pair step shows a timeout error when the key is never approved."""
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
        patch(
            "homeassistant.components.teslemetry.config_flow.asyncio.sleep",
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
    assert result["errors"] == {"base": "timeout"}


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
