"""Tests for the for the BMW Connected Drive integration."""


import respx

from homeassistant import config_entries
from homeassistant.components.bmw_connected_drive.const import (
    CONF_GCID,
    CONF_READ_ONLY,
    CONF_REFRESH_TOKEN,
    DOMAIN as BMW_DOMAIN,
)
from homeassistant.const import CONF_PASSWORD, CONF_REGION, CONF_USERNAME
from homeassistant.core import HomeAssistant

from tests.common import MockConfigEntry

FIXTURE_USER_INPUT = {
    CONF_USERNAME: "user@domain.com",
    CONF_PASSWORD: "p4ssw0rd",
    CONF_REGION: "rest_of_world",
}
FIXTURE_REFRESH_TOKEN = "SOME_REFRESH_TOKEN"
FIXTURE_GCID = "SOME_GCID"

FIXTURE_CONFIG_ENTRY = {
    "entry_id": "1",
    "domain": BMW_DOMAIN,
    "title": FIXTURE_USER_INPUT[CONF_USERNAME],
    "data": {
        CONF_USERNAME: FIXTURE_USER_INPUT[CONF_USERNAME],
        CONF_PASSWORD: FIXTURE_USER_INPUT[CONF_PASSWORD],
        CONF_REGION: FIXTURE_USER_INPUT[CONF_REGION],
        CONF_REFRESH_TOKEN: FIXTURE_REFRESH_TOKEN,
        CONF_GCID: FIXTURE_GCID,
    },
    "options": {CONF_READ_ONLY: False},
    "source": config_entries.SOURCE_USER,
    "unique_id": f"{FIXTURE_USER_INPUT[CONF_REGION]}-{FIXTURE_USER_INPUT[CONF_REGION]}",
}


async def setup_mocked_integration(hass: HomeAssistant) -> MockConfigEntry:
    """Mock a fully setup config entry and all components based on fixtures."""

    mock_config_entry = MockConfigEntry(**FIXTURE_CONFIG_ENTRY)
    mock_config_entry.add_to_hass(hass)

    assert await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    return mock_config_entry


def check_remote_service_call(router: respx.MockRouter):
    """Check if the last call was a successful remote service call."""
    last_event_status_call = next(
        iter(
            reversed(
                [c for c in router.calls if c.request.url.path.endswith("eventStatus")]
            )
        )
    )

    assert last_event_status_call is not None
    assert (
        last_event_status_call.request.url.path
        == "/eadrax-vrccs/v3/presentation/remote-commands/eventStatus"
    )
    assert last_event_status_call.has_response is True
    assert last_event_status_call.response.is_success is True
    assert last_event_status_call.response.json() == {"eventStatus": "EXECUTED"}
