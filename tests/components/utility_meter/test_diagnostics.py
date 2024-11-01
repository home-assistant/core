"""Test Utility Meter diagnostics."""

from aiohttp.test_utils import TestClient
from freezegun import freeze_time
import pytest
from syrupy import SnapshotAssertion
from syrupy.filters import props

from homeassistant.auth.models import Credentials
from homeassistant.components.utility_meter.const import DOMAIN
from homeassistant.components.utility_meter.sensor import ATTR_LAST_RESET
from homeassistant.core import HomeAssistant, State

from tests.common import (
    CLIENT_ID,
    MockConfigEntry,
    MockUser,
    mock_restore_cache_with_extra_data,
)
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def generate_new_hass_access_token(
    hass: HomeAssistant, hass_admin_user: MockUser, hass_admin_credential: Credentials
) -> str:
    """Return an access token to access Home Assistant."""
    await hass.auth.async_link_user(hass_admin_user, hass_admin_credential)

    refresh_token = await hass.auth.async_create_refresh_token(
        hass_admin_user, CLIENT_ID, credential=hass_admin_credential
    )
    return hass.auth.async_create_access_token(refresh_token)


def _get_test_client_generator(
    hass: HomeAssistant, aiohttp_client: ClientSessionGenerator, new_token: str
):
    """Return a test client generator.""."""

    async def auth_client() -> TestClient:
        return await aiohttp_client(
            hass.http.app, headers={"Authorization": f"Bearer {new_token}"}
        )

    return auth_client


@freeze_time("2024-04-06 00:00:00+00:00")
@pytest.mark.usefixtures("socket_enabled")
async def test_diagnostics(
    hass: HomeAssistant,
    aiohttp_client: ClientSessionGenerator,
    hass_admin_user: MockUser,
    hass_admin_credential: Credentials,
    snapshot: SnapshotAssertion,
) -> None:
    """Test generating diagnostics for a config entry."""

    # Setup the config entry
    config_entry = MockConfigEntry(
        data={},
        domain=DOMAIN,
        options={
            "cycle": "monthly",
            "delta_values": False,
            "name": "Energy Bill",
            "net_consumption": False,
            "offset": 0,
            "periodically_resetting": True,
            "source": "sensor.input1",
            "tariffs": [
                "tariff0",
                "tariff1",
            ],
        },
        title="Energy Bill",
    )

    last_reset = "2024-04-05T00:00:00+00:00"

    # Set up the sensors restore data
    mock_restore_cache_with_extra_data(
        hass,
        [
            (
                State(
                    "sensor.energy_bill_tariff0",
                    "3",
                    attributes={
                        ATTR_LAST_RESET: last_reset,
                    },
                ),
                {},
            ),
            (
                State(
                    "sensor.energy_bill_tariff1",
                    "7",
                    attributes={
                        ATTR_LAST_RESET: last_reset,
                    },
                ),
                {},
            ),
        ],
    )

    config_entry.add_to_hass(hass)
    assert await hass.config_entries.async_setup(config_entry.entry_id)
    await hass.async_block_till_done()

    # Since we are freezing time only when we enter this test, we need to
    # manually create a new token and clients since the token created by
    # the fixtures would not be valid.
    new_token = await generate_new_hass_access_token(
        hass, hass_admin_user, hass_admin_credential
    )

    diag = await get_diagnostics_for_config_entry(
        hass, _get_test_client_generator(hass, aiohttp_client, new_token), config_entry
    )

    assert diag == snapshot(exclude=props("entry_id", "created_at", "modified_at"))
