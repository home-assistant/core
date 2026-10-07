"""Test ViCare diagnostics."""

from unittest.mock import MagicMock, patch

from PyViCare.PyViCareUtils import PyViCareDeviceCommunicationError
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.core import HomeAssistant

from . import MODULE, setup_integration
from .conftest import Fixture, MockPyViCare

from tests.common import MockConfigEntry
from tests.components.diagnostics import get_diagnostics_for_config_entry
from tests.typing import ClientSessionGenerator


async def test_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_vicare_gas_boiler: MagicMock,
    snapshot: SnapshotAssertion,
) -> None:
    """Test diagnostics."""
    diag = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_vicare_gas_boiler
    )

    assert diag == snapshot(exclude=props("created_at", "modified_at"))


async def test_diagnostics_with_offline_device(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_vicare_gas_boiler: MagicMock,
) -> None:
    """Test that an offline gateway on one device does not abort diagnostics."""
    config_entry = hass.config_entries.async_entries("vicare")[0]
    devices = config_entry.runtime_data.client.all_devices

    # Force the first device to fail with GATEWAY_OFFLINE; the rest must still dump.
    devices[0].dump_secure = MagicMock(
        side_effect=PyViCareDeviceCommunicationError(
            {"extendedPayload": {"reason": "GATEWAY_OFFLINE"}}
        )
    )

    diag = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_vicare_gas_boiler
    )

    assert len(diag["data"]) == len(devices)
    error_entry = diag["data"][0]
    assert "error" in error_entry
    assert "GATEWAY_OFFLINE" in error_entry["error"]
    assert error_entry["device"]["id"] == devices[0].device_id


async def test_diagnostics_scopes_features_to_their_device(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Devices sharing a gateway must not each dump the whole gateway payload."""
    fixtures: list[Fixture] = [
        Fixture({"type:boiler"}, "vicare/Vitodens300W.json", gateway_id="gateway0"),
        Fixture({"type:heatpump"}, "vicare/Vitocal250A.json", gateway_id="gateway0"),
    ]
    with (
        patch(
            "homeassistant.helpers.config_entry_oauth2_flow.OAuth2Session.async_ensure_token_valid",
        ),
        patch(
            f"{MODULE}._setup_vicare_api",
            return_value=MockPyViCare(fixtures).as_vicare_data(),
        ),
    ):
        await setup_integration(hass, mock_config_entry)

    diag = await get_diagnostics_for_config_entry(hass, hass_client, mock_config_entry)

    dumps = {entry["device"]["id"]: entry["data"] for entry in diag["data"]}
    # 167 and 325 features; without scoping both would dump all 492.
    assert [len(dumps["deviceId0"]), len(dumps["deviceId1"])] == [167, 325]
    for device_id in ("deviceId0", "deviceId1"):
        assert {
            feature["uri"].split("/devices/")[1].split("/")[0]
            for feature in dumps[device_id]
        } == {device_id}
