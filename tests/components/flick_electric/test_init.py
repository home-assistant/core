"""Test the Flick Electric config flow."""

from unittest.mock import patch

from pyflick.authentication import AuthException

from homeassistant.components.flick_electric.const import CONF_ACCOUNT_ID, DOMAIN
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_PASSWORD, CONF_USERNAME
from homeassistant.core import HomeAssistant

from . import CONF, _mock_flick_price

from tests.common import MockConfigEntry


async def test_init_auth_failure_triggers_auth(hass: HomeAssistant) -> None:
    """Test reauth flow is triggered when username/password is wrong."""
    with (
        patch(
            "homeassistant.components.flick_electric.HassFlickAuth.async_get_access_token",
            side_effect=AuthException,
        ),
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={**CONF},
            title="123 Fake St",
            unique_id="1234",
            version=2,
        )
        entry.add_to_hass(hass)

        # Ensure setup fails
        assert not await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is ConfigEntryState.SETUP_ERROR

        # Ensure reauth flow is triggered
        await hass.async_block_till_done()
        assert len(hass.config_entries.flow.async_progress()) == 1


async def test_init_migration_single_account(hass: HomeAssistant) -> None:
    """Test migration with single account."""
    with (
        patch(
            "homeassistant.components.flick_electric.HassFlickAuth.async_get_access_token",
            return_value="123456789abcdef",
        ),
        patch(
            "homeassistant.components.flick_electric.FlickAPI.getCustomerAccounts",
            return_value=[
                {
                    "id": "1234",
                    "status": "active",
                    "address": "123 Fake St",
                    "main_consumer": {"supply_node_ref": "123"},
                }
            ],
        ),
        patch(
            "homeassistant.components.flick_electric.FlickAPI.getPricing",
            return_value=_mock_flick_price(),
        ),
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_USERNAME: CONF[CONF_USERNAME],
                CONF_PASSWORD: CONF[CONF_PASSWORD],
            },
            title=CONF_USERNAME,
            unique_id=CONF_USERNAME,
            version=1,
        )
        entry.add_to_hass(hass)

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        assert len(hass.config_entries.flow.async_progress()) == 0
        assert entry.state is ConfigEntryState.LOADED
        assert entry.version == 2
        assert entry.unique_id == CONF[CONF_ACCOUNT_ID]
        assert entry.data == CONF


async def test_init_migration_multi_account_reauth(hass: HomeAssistant) -> None:
    """Test migration triggers reauth with multiple accounts."""
    with (
        patch(
            "homeassistant.components.flick_electric.HassFlickAuth.async_get_access_token",
            return_value="123456789abcdef",
        ),
        patch(
            "homeassistant.components.flick_electric.FlickAPI.getCustomerAccounts",
            return_value=[
                {
                    "id": "1234",
                    "status": "active",
                    "address": "123 Fake St",
                    "main_consumer": {"supply_node_ref": "123"},
                },
                {
                    "id": "5678",
                    "status": "active",
                    "address": "456 Fake St",
                    "main_consumer": {"supply_node_ref": "456"},
                },
            ],
        ),
        patch(
            "homeassistant.components.flick_electric.FlickAPI.getPricing",
            return_value=_mock_flick_price(),
        ),
    ):
        entry = MockConfigEntry(
            domain=DOMAIN,
            data={
                CONF_USERNAME: CONF[CONF_USERNAME],
                CONF_PASSWORD: CONF[CONF_PASSWORD],
            },
            title=CONF_USERNAME,
            unique_id=CONF_USERNAME,
            version=1,
        )
        entry.add_to_hass(hass)

        # ensure setup fails
        assert not await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is ConfigEntryState.MIGRATION_ERROR
        await hass.async_block_till_done()

        # Ensure reauth flow is triggered
        await hass.async_block_till_done()
        assert len(hass.config_entries.flow.async_progress()) == 1
