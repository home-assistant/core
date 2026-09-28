"""Tests for EnergyID directive actions."""

import datetime as dt
from unittest.mock import AsyncMock, MagicMock

from aiohttp import ClientError
from energyid_webhooks.directives import (
    DirectiveData,
    DirectiveResource,
    DirectiveSignal,
    SignalProvider,
)

from homeassistant.components.energyid.const import CONF_ENABLE_DIRECTIVES, DOMAIN
from homeassistant.components.energyid.sensor import SERVICE_GET_DIRECTIVE_SCHEDULE
from homeassistant.const import ATTR_ENTITY_ID, STATE_UNAVAILABLE
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from tests.common import MockConfigEntry

DIRECTIVE_ID = "11111111-1111-1111-1111-111111111111"


def _directive_fixture() -> tuple[DirectiveResource, DirectiveData]:
    """Return one EnergyID directive schedule."""
    now = dt_util.utcnow().replace(second=0, microsecond=0)
    resource = DirectiveResource(
        id=DIRECTIVE_ID,
        title="Community planner",
        description="Community balance forecast",
        properties=("color", "signal"),
        signal_provider=SignalProvider(
            id="community",
            display_name="Energy community",
            logo_url="https://example.com/community.svg",
        ),
    )
    schedule = DirectiveData(
        title=resource.title,
        description=resource.description,
        interval="PT15M",
        data=(
            DirectiveSignal(
                timestamp=now,
                signal="++",
                color="#00750e",
                raw_value=1.0,
            ),
            DirectiveSignal(
                timestamp=now + dt.timedelta(minutes=15),
                signal="0",
                color="#EBEBEB",
                raw_value=0.0,
            ),
        ),
    )
    return resource, schedule


async def test_get_directive_schedule(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the action returns the complete directive schedule."""
    resource, schedule = _directive_fixture()
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_ENABLE_DIRECTIVES: True}
    )
    mock_webhook_client.api_access_token = "device-token"
    mock_webhook_client.get_directives = AsyncMock(return_value=[resource])
    mock_webhook_client.get_directive_data = AsyncMock(return_value=schedule)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    [registry_entry] = er.async_entries_for_config_entry(
        entity_registry, mock_config_entry.entry_id
    )
    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_DIRECTIVE_SCHEDULE,
        {},
        target={ATTR_ENTITY_ID: registry_entry.entity_id},
        blocking=True,
        return_response=True,
    )

    returned = response[registry_entry.entity_id]
    assert returned["title"] == "Community planner"
    assert returned["provider"]["display_name"] == "Energy community"
    assert returned["interval"] == "PT15M"
    assert returned["data"] == [
        {
            "timestamp": schedule.data[0].timestamp.isoformat(),
            "signal": "++",
            "color": "#00750e",
            "raw_value": 1.0,
        },
        {
            "timestamp": schedule.data[1].timestamp.isoformat(),
            "signal": "0",
            "color": "#EBEBEB",
            "raw_value": 0.0,
        },
    ]
    assert schedule.data[1].timestamp - schedule.data[0].timestamp == dt.timedelta(
        minutes=15
    )
    # The schedule comes from coordinator data, so setup made the only call.
    assert mock_webhook_client.get_directive_data.await_count == 1


async def test_get_directive_schedule_skips_unavailable_directive(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_webhook_client: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test the action only answers for directives whose schedule was fetched."""
    resource, schedule = _directive_fixture()
    failing_resource = DirectiveResource(
        id="22222222-2222-2222-2222-222222222222",
        title="Unavailable planner",
        description="Broken upstream",
        properties=("color", "signal"),
        signal_provider=SignalProvider(
            id="provider-2",
            display_name="Provider 2",
            logo_url=None,
        ),
    )
    hass.config_entries.async_update_entry(
        mock_config_entry, options={CONF_ENABLE_DIRECTIVES: True}
    )
    mock_webhook_client.api_access_token = "device-token"
    mock_webhook_client.get_directives = AsyncMock(
        return_value=[resource, failing_resource]
    )

    async def get_directive_data(directive_id: str) -> DirectiveData:
        if directive_id == failing_resource.id:
            raise ClientError("upstream failed")
        return schedule

    mock_webhook_client.get_directive_data = AsyncMock(side_effect=get_directive_data)

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    entity_ids = {
        registry_entry.unique_id.removeprefix(
            f"{mock_config_entry.entry_id}_"
        ): registry_entry.entity_id
        for registry_entry in er.async_entries_for_config_entry(
            entity_registry, mock_config_entry.entry_id
        )
    }
    assert hass.states.get(entity_ids[failing_resource.id]).state == STATE_UNAVAILABLE

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_GET_DIRECTIVE_SCHEDULE,
        {},
        target={ATTR_ENTITY_ID: list(entity_ids.values())},
        blocking=True,
        return_response=True,
    )

    assert set(response) == {entity_ids[resource.id]}
    assert response[entity_ids[resource.id]]["title"] == "Community planner"
