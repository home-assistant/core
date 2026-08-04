"""Test the Frontier Silicon init flow."""

import logging
from typing import TypeVar, overload
from unittest.mock import patch

from afsapi import Endpoint, FSNotImplementedError, ListEndpoint
import pytest

from homeassistant.components.frontier_silicon.const import DOMAIN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr, entity_registry as er

from tests.common import MockConfigEntry

_LOGGER = logging.getLogger(__name__)

V = TypeVar("V", bound=str | int)
ListValue = TypeVar("ListValue")


@overload
def mock_get(endpoint: Endpoint[str]) -> str | None: ...


@overload
def mock_get(endpoint: Endpoint[int]) -> int | None: ...


@overload
def mock_get(
    endpoint: ListEndpoint[ListValue],
) -> list[tuple[str, ListValue]]: ...


def mock_get(
    endpoint: Endpoint[str] | Endpoint[int] | ListEndpoint[ListValue],
) -> str | int | list[tuple[str, ListValue]] | None:
    """Mock GET from an AFSAPI endpoint enough to run through init."""
    match endpoint.path:
        case "netRemote.sys.clock.dst":
            return True
        case "netRemote.sys.power":
            return True
        case "netRemote.play.status":
            return 0
        case "netRemote.sys.caps.validModes":
            return [(0, {"id": "mocked_mode0", "label": "MockedMode"})]
        case "netRemote.play.caps":
            return 0
        case "netRemote.sys.caps.eqPresets":
            return [(0, {"id": "mocked_eqpreset0", "label": "MockedEq"})]
        case _:
            _LOGGER.warning("Unhandled GET: %s", endpoint.path)
            return None
    return True


async def test_device_in_dr(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
) -> None:
    """Test Frontier Silicon device registry data."""
    with patch(
        "afsapi.AFSAPI.get",
        side_effect=mock_get,
    ):
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        devices = dr.async_entries_for_config_entry(
            device_registry, config_entry.entry_id
        )

        assert len(devices) == 1
        device_entry = devices[0]
        assert DOMAIN in [
            id_entry
            for id_tuple in list(device_entry.identifiers)
            for id_entry in id_tuple
        ]


@pytest.mark.parametrize(
    ("get_dst_return_value", "get_dst_side_effect"),
    [(True, None), (None, FSNotImplementedError)],
)
async def test_entities_in_er(
    hass: HomeAssistant,
    config_entry: MockConfigEntry,
    device_registry: dr.DeviceRegistry,
    entity_registry: er.EntityRegistry,
    get_dst_return_value: bool | None,
    get_dst_side_effect: Exception | None,
) -> None:
    """Test the expected number of entities are created depending on if the device implements the DST node."""
    with (
        patch(
            "afsapi.AFSAPI.get",
            side_effect=mock_get,
        ),
        patch(
            "afsapi.AFSAPI.get_dst",
            return_value=get_dst_return_value,
            side_effect=get_dst_side_effect,
        ),
    ):
        config_entry.add_to_hass(hass)
        await hass.config_entries.async_setup(config_entry.entry_id)
        await hass.async_block_till_done()

        devices = dr.async_entries_for_config_entry(
            device_registry, config_entry.entry_id
        )

        assert len(devices) == 1
        device_entry = devices[0]

        expected_num_entities = 2 if get_dst_side_effect is None else 1
        entities = er.async_entries_for_device(entity_registry, device_entry.id)
        assert len(entities) == expected_num_entities
