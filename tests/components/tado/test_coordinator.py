"""Test the Tado coordinator."""

from unittest.mock import MagicMock

import pytest
from requests import RequestException

from homeassistant.components.tado import CONF_REFRESH_TOKEN, DOMAIN
from homeassistant.components.tado.coordinator import TadoDataUpdateCoordinator
from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import UpdateFailed

from tests.common import MockConfigEntry


async def test_refresh_token_is_persisted_even_if_update_fails(
    hass: HomeAssistant,
) -> None:
    """A rotated refresh token must be saved even if a later API call fails.

    Tado rotates the refresh token whenever the short-lived access token is
    refreshed, which PyTado does lazily on the first API call of a cycle
    (``get_me``/``get_zones``/``get_devices``). If a later call in that same
    cycle fails, the newly rotated token must still be persisted to the
    config entry - otherwise a restart before the next successful cycle
    leaves Home Assistant holding a stale, already-invalidated token and
    forces the user to re-authenticate (home-assistant/core#176592).
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_REFRESH_TOKEN: "old-token"},
        unique_id="1",
        version=2,
    )
    entry.add_to_hass(hass)

    tado = MagicMock()
    tado.get_me.return_value = {"homes": [{"id": 1, "name": "Home"}]}
    tado.get_zones.return_value = []
    # Empty devices makes _async_update_devices raise UpdateFailed, simulating
    # a failure that happens *after* the token has already rotated during the
    # earlier get_me/get_zones/get_devices calls above.
    tado.get_devices.return_value = []
    # The token has already rotated in PyTado's in-memory client by the time
    # this cycle fails.
    tado.get_refresh_token.return_value = "new-token"

    coordinator = TadoDataUpdateCoordinator(hass, entry, tado)

    with pytest.raises(UpdateFailed):
        await coordinator._async_update_data()

    assert entry.data[CONF_REFRESH_TOKEN] == "new-token"


async def test_refresh_token_is_persisted_on_success(hass: HomeAssistant) -> None:
    """Sanity check: the existing happy-path persist behavior still works."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_REFRESH_TOKEN: "old-token"},
        unique_id="1",
        version=2,
    )
    entry.add_to_hass(hass)

    tado = MagicMock()
    tado.get_me.return_value = {"homes": [{"id": 1, "name": "Home"}]}
    tado.get_zones.return_value = []
    tado.get_devices.return_value = []
    tado.get_zone_states.return_value = {"zoneStates": {}}
    tado.get_weather.return_value = {}
    tado.get_home_state.return_value = {}
    tado.get_refresh_token.return_value = "new-token"
    tado.rate_limit_info.return_value = {"remaining": "999"}

    coordinator = TadoDataUpdateCoordinator(hass, entry, tado)

    # Avoid the empty-devices UpdateFailed short-circuit so we exercise the
    # full happy path.
    with pytest.MonkeyPatch().context() as mp:
        mp.setattr(coordinator, "_async_update_devices", _return_empty_dict)
        await coordinator._async_update_data()

    assert entry.data[CONF_REFRESH_TOKEN] == "new-token"


async def test_empty_refresh_token_does_not_clear_stored_token(
    hass: HomeAssistant,
) -> None:
    """A falsy refresh token from PyTado must not overwrite the stored one.

    ``get_refresh_token`` can return ``None`` (or an empty string) when
    PyTado has not rotated the token this cycle. The persist check must
    require the new value to be truthy *and* different, otherwise a falsy
    result would compare unequal to the stored token and clear it.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_REFRESH_TOKEN: "old-token"},
        unique_id="1",
        version=2,
    )
    entry.add_to_hass(hass)

    tado = MagicMock()
    tado.get_me.return_value = {"homes": [{"id": 1, "name": "Home"}]}
    tado.get_zones.return_value = []
    tado.get_devices.return_value = []
    tado.get_zone_states.return_value = {"zoneStates": {}}
    tado.get_weather.return_value = {}
    tado.get_home_state.return_value = {}
    tado.get_refresh_token.return_value = None
    tado.rate_limit_info.return_value = {"remaining": "999"}

    coordinator = TadoDataUpdateCoordinator(hass, entry, tado)

    with pytest.MonkeyPatch().context() as mp:
        mp.setattr(coordinator, "_async_update_devices", _return_empty_dict)
        await coordinator._async_update_data()

    assert entry.data[CONF_REFRESH_TOKEN] == "old-token"


async def test_rate_limit_reached_raises_update_failed(
    hass: HomeAssistant,
) -> None:
    """A RequestException with no rate limit remaining raises a rate-limit error.

    ``_load_tado_data`` can fail outright (e.g. the initial ``get_me`` call),
    in which case the coordinator checks Tado's rate limit to give a more
    specific error message. This also exercises the ``finally`` block: even
    though the initial call failed, the (possibly already rotated) refresh
    token must still be persisted.
    """
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_REFRESH_TOKEN: "old-token"},
        unique_id="1",
        version=2,
    )
    entry.add_to_hass(hass)

    tado = MagicMock()
    tado.get_me.side_effect = RequestException("boom")
    tado.get_refresh_token.return_value = "new-token"
    tado.rate_limit_info.return_value = {"remaining": "0"}

    coordinator = TadoDataUpdateCoordinator(hass, entry, tado)

    with pytest.raises(UpdateFailed, match="rate limit reached"):
        await coordinator._async_update_data()

    assert entry.data[CONF_REFRESH_TOKEN] == "new-token"


async def test_request_exception_without_rate_limit_raises_update_failed(
    hass: HomeAssistant,
) -> None:
    """A RequestException with rate limit remaining raises a generic setup error."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_REFRESH_TOKEN: "old-token"},
        unique_id="1",
        version=2,
    )
    entry.add_to_hass(hass)

    tado = MagicMock()
    tado.get_me.side_effect = RequestException("boom")
    tado.get_refresh_token.return_value = "old-token"
    tado.rate_limit_info.return_value = {"remaining": "999"}

    coordinator = TadoDataUpdateCoordinator(hass, entry, tado)

    with pytest.raises(UpdateFailed, match="Error during Tado setup"):
        await coordinator._async_update_data()


async def _return_empty_dict(*_args, **_kwargs) -> dict:
    return {}
