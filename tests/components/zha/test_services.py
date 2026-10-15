"""Tests for the ZHA services."""

import pytest

from homeassistant.components.zha.const import DOMAIN
from homeassistant.components.zha.services import (
    SERVICE_ISSUE_ZIGBEE_CLUSTER_COMMAND,
    SERVICE_ISSUE_ZIGBEE_GROUP_COMMAND,
    SERVICE_PERMIT,
    SERVICE_REMOVE,
    SERVICE_SET_ZIGBEE_CLUSTER_ATTRIBUTE,
    SERVICE_WARNING_DEVICE_SQUAWK,
    SERVICE_WARNING_DEVICE_WARN,
)
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import ServiceValidationError
from homeassistant.setup import async_setup_component

IEEE_SWITCH_DEVICE = "01:2d:6f:00:0a:90:69:e7"


async def test_services_registered_without_gateway(hass: HomeAssistant) -> None:
    """Test the actions are registered during component setup."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    for service in (
        SERVICE_PERMIT,
        SERVICE_REMOVE,
        SERVICE_SET_ZIGBEE_CLUSTER_ATTRIBUTE,
        SERVICE_ISSUE_ZIGBEE_CLUSTER_COMMAND,
        SERVICE_ISSUE_ZIGBEE_GROUP_COMMAND,
        SERVICE_WARNING_DEVICE_SQUAWK,
        SERVICE_WARNING_DEVICE_WARN,
    ):
        assert hass.services.has_service(DOMAIN, service)


@pytest.mark.parametrize(
    ("service", "data"),
    [
        pytest.param(SERVICE_PERMIT, {}, id="permit"),
        pytest.param(SERVICE_REMOVE, {"ieee": IEEE_SWITCH_DEVICE}, id="remove"),
        pytest.param(
            SERVICE_SET_ZIGBEE_CLUSTER_ATTRIBUTE,
            {
                "ieee": IEEE_SWITCH_DEVICE,
                "endpoint_id": 1,
                "cluster_id": 6,
                "attribute": 0,
                "value": 1,
            },
            id="set_zigbee_cluster_attribute",
        ),
        pytest.param(
            SERVICE_ISSUE_ZIGBEE_CLUSTER_COMMAND,
            {
                "ieee": IEEE_SWITCH_DEVICE,
                "endpoint_id": 1,
                "cluster_id": 6,
                "command": 0,
                "command_type": "server",
                "params": {},
            },
            id="issue_zigbee_cluster_command",
        ),
        pytest.param(
            SERVICE_ISSUE_ZIGBEE_GROUP_COMMAND,
            {"group": 1, "cluster_id": 6, "command": 0},
            id="issue_zigbee_group_command",
        ),
        pytest.param(
            SERVICE_WARNING_DEVICE_SQUAWK,
            {"ieee": IEEE_SWITCH_DEVICE},
            id="warning_device_squawk",
        ),
        pytest.param(
            SERVICE_WARNING_DEVICE_WARN,
            {"ieee": IEEE_SWITCH_DEVICE},
            id="warning_device_warn",
        ),
    ],
)
async def test_service_without_gateway_raises(
    hass: HomeAssistant, service: str, data: dict
) -> None:
    """Test the actions raise a user-facing error when no gateway is loaded."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    with pytest.raises(ServiceValidationError) as err:
        await hass.services.async_call(DOMAIN, service, data, blocking=True)

    assert err.value.translation_domain == DOMAIN
    assert err.value.translation_key == "no_gateway"
