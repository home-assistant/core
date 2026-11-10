"""Test the Matter helpers."""

from unittest.mock import MagicMock

from chip.clusters import Objects as clusters
from matter_server.client.models.node import MatterNode
import pytest
from pytest_homeassistant.common import MockConfigEntry

from homeassistant.components.matter.const import DOMAIN
from homeassistant.components.matter.helpers import (
    get_device_id,
    get_node_from_device_entry,
    write_error_status,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr

from .common import setup_integration_with_node_fixture


@pytest.mark.parametrize("node_fixture", ["device_diagnostics"])
async def test_get_device_id(
    hass: HomeAssistant,
    matter_client: MagicMock,
    matter_node: MatterNode,
) -> None:
    """Test get_device_id."""
    device_id = get_device_id(matter_client.server_info, matter_node.endpoints[0])

    assert device_id == "00000000000004D2-0000000000000005-MatterNodeDevice"


async def test_get_node_from_device_entry(
    hass: HomeAssistant,
    device_registry: dr.DeviceRegistry,
    matter_client: MagicMock,
) -> None:
    """Test get_node_from_device_entry."""
    other_domain = "other_domain"
    other_config_entry = MockConfigEntry(domain=other_domain)
    other_config_entry.add_to_hass(hass)
    other_device_entry = device_registry.async_get_or_create(
        config_entry_id=other_config_entry.entry_id,
        identifiers={(other_domain, "1234")},
    )
    node = await setup_integration_with_node_fixture(
        hass, "device_diagnostics", matter_client
    )
    config_entry = hass.config_entries.async_entries(DOMAIN)[0]
    device_entry = dr.async_entries_for_config_entry(
        device_registry, config_entry.entry_id
    )[0]
    assert device_entry
    node_from_device_entry = get_node_from_device_entry(hass, device_entry)

    assert node_from_device_entry is node

    # test non-Matter device returns None
    assert get_node_from_device_entry(hass, other_device_entry) is None

    matter_client.server_info = None

    # test non-initialized server raises RuntimeError
    with pytest.raises(RuntimeError) as runtime_error:
        node_from_device_entry = get_node_from_device_entry(hass, device_entry)

    assert "Matter server information is not available" in str(runtime_error.value)


SUCCESS = clusters.Globals.Enums.status.kSuccess
CONSTRAINT_ERROR = clusters.Globals.Enums.status.kConstraintError
BUSY = clusters.Globals.Enums.status.kBusy


def _write_result(attribute_id: int, status: int) -> dict:
    """Return one path's result, as the Matter Server answers a write."""
    return {
        "Path": {"EndpointId": 1, "ClusterId": 513, "AttributeId": attribute_id},
        "Status": status,
    }


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        pytest.param(None, None, id="no_result"),
        pytest.param([], None, id="empty"),
        pytest.param([_write_result(19, SUCCESS)], None, id="success"),
        pytest.param(
            [_write_result(19, SUCCESS), _write_result(20, SUCCESS)],
            None,
            id="all_success",
        ),
        pytest.param(
            [_write_result(19, CONSTRAINT_ERROR)], CONSTRAINT_ERROR, id="failure"
        ),
        pytest.param(
            [_write_result(19, SUCCESS), _write_result(20, CONSTRAINT_ERROR)],
            CONSTRAINT_ERROR,
            id="success_then_failure",
        ),
        pytest.param(
            [_write_result(19, CONSTRAINT_ERROR), _write_result(20, SUCCESS)],
            CONSTRAINT_ERROR,
            id="failure_then_success",
        ),
        pytest.param(
            [_write_result(19, BUSY), _write_result(20, CONSTRAINT_ERROR)],
            BUSY,
            id="first_failure_wins",
        ),
        pytest.param([{"Path": {}}, "unexpected"], None, id="no_status"),
    ],
)
def test_write_error_status(result: object, expected: int | None) -> None:
    """Test the first unsuccessful status of a write response is returned."""
    assert write_error_status(result) == expected
