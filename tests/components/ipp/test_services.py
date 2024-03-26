"""Test IPP services."""

from unittest.mock import AsyncMock

from syrupy import SnapshotAssertion

from homeassistant.components.ipp.const import (
    CONF_BASE_PATH,
    DOMAIN,
    SERVICE_IPP_ATTR_OPERATION,
    SERVICE_IPP_ATTR_PAYLOAD,
    SERVICE_IPP_DUMP,
)
from homeassistant.const import CONF_HOST, CONF_PORT, CONF_SSL, CONF_VERIFY_SSL
from homeassistant.core import HomeAssistant
from homeassistant.setup import async_setup_component

from . import load_binary_fixture


async def test_dump(
    hass: HomeAssistant,
    mock_ipp_services: AsyncMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test `ipp.dump` service."""
    assert await async_setup_component(hass, DOMAIN, {})
    await hass.async_block_till_done()

    binary_data = load_binary_fixture("get-printer-attributes.bin")
    mock_ipp_services.raw.return_value = binary_data

    response = await hass.services.async_call(
        DOMAIN,
        SERVICE_IPP_DUMP,
        {
            CONF_HOST: "",
            CONF_PORT: 631,
            CONF_BASE_PATH: "ipp/print",
            CONF_SSL: True,
            CONF_VERIFY_SSL: True,
            SERVICE_IPP_ATTR_OPERATION: "GET_PRINTER_ATTRIBUTES",
            SERVICE_IPP_ATTR_PAYLOAD: {
                "operation-attributes-tag": {
                    "requested-attributes": [
                        "printer-device-id",
                        "printer-name",
                        "printer-type",
                        "printer-location",
                        "printer-info",
                        "printer-make-and-model",
                        "printer-state",
                        "printer-state-message",
                        "printer-state-reason",
                        "printer-supply",
                        "printer-up-time",
                        "printer-uri-supported",
                        "device-uri",
                        "printer-is-shared",
                        "printer-more-info",
                        "printer-firmware-string-version",
                        "marker-colors",
                        "marker-high-levels",
                        "marker-levels",
                        "marker-low-levels",
                        "marker-names",
                        "marker-types",
                    ],
                },
            },
        },
        blocking=True,
        return_response=True,
    )

    assert response == snapshot
