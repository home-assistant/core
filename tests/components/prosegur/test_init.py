"""Tests prosegur setup."""
from unittest.mock import MagicMock, patch

from pytest import mark

from homeassistant.components.prosegur import DOMAIN

from tests.common import MockConfigEntry


@mark.parametrize(
    "error",
    [
        ConnectionRefusedError,
        ConnectionError,
    ],
)
async def test_setup_entry_fail_retrieve(hass, error):
    """Test loading the Prosegur entry."""

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "username": "test-username",
            "password": "test-password",
            "country": "PT",
            "contract": "xpto",
        },
    )
    config_entry.add_to_hass(hass)

    with patch(
        "pyprosegur.auth.Auth.login",
        side_effect=error,
    ):
        assert not await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()


async def test_unload_entry(hass, aioclient_mock):
    """Test unloading the Prosegur entry."""

    aioclient_mock.post(
        "https://smart.prosegur.com/smart-server/ws/access/login",
        json={"data": {"token": "123456789"}},
    )

    config_entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "username": "test-username",
            "password": "test-password",
            "country": "PT",
            "contract": "xpto",
        },
    )
    config_entry.add_to_hass(hass)

    install = MagicMock()
    install.contract = "123"

    with patch(
        "homeassistant.components.prosegur.config_flow.Installation.retrieve",
        return_value=install,
    ):

        assert await hass.config_entries.async_setup(config_entry.entry_id)

        await hass.async_block_till_done()

        assert await hass.config_entries.async_unload(config_entry.entry_id)
