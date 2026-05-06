"""Test Gardena Bluetooth text entities."""

from unittest.mock import Mock

from gardena_bluetooth.const import AquaContourContours, AquaContourPosition
from habluetooth import BluetoothServiceInfo
import pytest
from syrupy.assertion import SnapshotAssertion

from homeassistant.components.text import (
    ATTR_VALUE,
    DOMAIN as TEXT_DOMAIN,
    SERVICE_SET_VALUE,
)
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import AQUA_CONTOUR_SERVICE_INFO, setup_entry

from tests.common import snapshot_platform


@pytest.mark.parametrize(
    ("service_info", "raw"),
    [
        pytest.param(
            AQUA_CONTOUR_SERVICE_INFO,
            {
                AquaContourPosition.position_name_1.uuid: b"Position 1\x00",
                AquaContourPosition.position_name_2.uuid: b"Position 2\x00",
                AquaContourPosition.position_name_3.uuid: b"Position 3\x00",
                AquaContourPosition.position_name_4.uuid: b"Position 4\x00",
                AquaContourPosition.position_name_5.uuid: b"Position 5\x00",
                AquaContourContours.contour_name_1.uuid: b"Contour 1\x00",
                AquaContourContours.contour_name_2.uuid: b"Contour 2\x00",
                AquaContourContours.contour_name_3.uuid: b"Contour 3\x00",
                AquaContourContours.contour_name_4.uuid: b"Contour 4\x00",
                AquaContourContours.contour_name_5.uuid: b"Contour 5\x00",
            },
            id="aqua_contour",
        ),
    ],
)
async def test_setup(
    hass: HomeAssistant,
    mock_read_char_raw: dict[str, bytes],
    service_info: BluetoothServiceInfo,
    raw: dict[str, bytes],
    entity_registry: er.EntityRegistry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test text entities."""
    mock_read_char_raw.update(raw)

    entry = await setup_entry(
        hass, platforms=[Platform.TEXT], service_info=service_info
    )
    await snapshot_platform(hass, entity_registry, snapshot, entry.entry_id)


async def test_text_set_value(
    hass: HomeAssistant,
    mock_read_char_raw: dict[str, bytes],
    mock_client: Mock,
) -> None:
    """Test setting text value."""
    mock_read_char_raw[AquaContourPosition.position_name_1.uuid] = b"Position 1\x00"

    await setup_entry(
        hass, platforms=[Platform.TEXT], service_info=AQUA_CONTOUR_SERVICE_INFO
    )

    await hass.services.async_call(
        TEXT_DOMAIN,
        SERVICE_SET_VALUE,
        {
            ATTR_ENTITY_ID: "text.mock_title_position_1",
            ATTR_VALUE: "New Position Name",
        },
        blocking=True,
    )

    assert len(mock_client.write_char.mock_calls) == 1
    args = mock_client.write_char.mock_calls[0].args
    assert args[0] == AquaContourPosition.position_name_1
    assert args[1] == "New Position Name"
