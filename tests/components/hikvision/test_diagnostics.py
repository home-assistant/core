"""Test Hikvision diagnostics."""

import asyncio
import json
import math
import threading
from unittest.mock import MagicMock

import pyhik
from pyhik.image import ImageSetting, ImageSettingType
from pyhik.isapi import ISAPIConnectionError, RawResponse
import pytest
from pytest_homeassistant.common import MockConfigEntry, async_load_fixture
from pytest_homeassistant.components.diagnostics import get_diagnostics_for_config_entry
from pytest_homeassistant.typing import ClientSessionGenerator
from syrupy.assertion import SnapshotAssertion
from syrupy.filters import props

from homeassistant.components.hikvision.const import DOMAIN
from homeassistant.components.hikvision.diagnostics import (
    async_get_config_entry_diagnostics,
)
from homeassistant.config_entries import SOURCE_REAUTH
from homeassistant.core import CoreState, HomeAssistant
from homeassistant.helpers import entity_registry as er

from . import setup_integration
from .conftest import TEST_DEVICE_ID

CAPABILITIES = "/ISAPI/Image/channels/1/capabilities"
VALUES = "/ISAPI/Image/channels/1"


@pytest.fixture
async def raw_documents(
    hass: HomeAssistant, mock_image_settings: MagicMock
) -> dict[str, str]:
    """Make the mocked camera send its image documents when asked directly."""
    documents = {
        CAPABILITIES: await async_load_fixture(hass, "image_capabilities.xml", DOMAIN),
        VALUES: await async_load_fixture(hass, "image_values.xml", DOMAIN),
    }
    mock_image_settings.request_raw.side_effect = lambda method, endpoint: RawResponse(
        200, documents[endpoint].encode()
    )
    return documents


@pytest.mark.usefixtures("raw_documents", "mock_hikcamera", "mock_image_settings")
async def test_entry_diagnostics(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    snapshot: SnapshotAssertion,
) -> None:
    """Test the diagnostics of a camera with image settings."""
    await setup_integration(hass, mock_config_entry)

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    # The version of the installed library changes with every bump
    assert result.pop("pyhik_version") == pyhik.__version__
    assert result == snapshot(exclude=props("created_at", "modified_at", "entry_id"))


@pytest.mark.usefixtures("raw_documents", "mock_hikcamera", "mock_image_settings")
async def test_credentials_are_redacted(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test nothing that identifies the camera is reported."""
    await setup_integration(hass, mock_config_entry)

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    data = result["entry"]["data"]
    assert data["host"] == "**REDACTED**"
    assert data["username"] == "**REDACTED**"
    assert data["password"] == "**REDACTED**"
    assert result["entry"]["title"] == "**REDACTED**"
    assert result["entry"]["unique_id"] == "**REDACTED**"


@pytest.mark.usefixtures("raw_documents", "mock_hikcamera")
async def test_unknown_settings_and_values_are_reported(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test a setting the integration has no entity for can be reported."""
    mock_image_settings.get_image_settings.return_value = [
        ImageSetting(
            "Gain/GainLevel", ImageSettingType.NUMBER, min_value=0, max_value=100
        ),
        ImageSetting("Foo/barMode", ImageSettingType.SELECT, options=["a", "b"]),
    ]
    mock_image_settings.get_image_values.return_value = {
        "Gain/GainLevel": "50",
        "Foo/barMode": "a",
        "Foo/unlisted": "1",
    }
    await setup_integration(hass, mock_config_entry)

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    settings = result["image_settings"]["settings"]
    assert settings["Gain/GainLevel"]["known"] is True
    assert settings["Gain/GainLevel"]["value"] == "50"
    assert settings["Foo/barMode"]["known"] is False
    assert settings["Foo/barMode"]["options"] == ["a", "b"]
    assert result["image_settings"]["other_values"] == {"Foo/unlisted": "1"}


@pytest.mark.usefixtures("raw_documents", "mock_hikcamera")
async def test_a_setting_that_is_no_longer_accepted_is_not_known(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    entity_registry: er.EntityRegistry,
) -> None:
    """Test an entity that an earlier setup left in the registry does not count."""
    mock_config_entry.add_to_hass(hass)
    entity_registry.async_get_or_create(
        "select",
        DOMAIN,
        f"{TEST_DEVICE_ID}_image_scene_mode",
        config_entry=mock_config_entry,
    )
    mock_image_settings.get_image_settings.return_value = [
        # Two values that would become the same option, so there is no entity.
        ImageSetting("Scene/mode", ImageSettingType.SELECT, options=["Auto", "auto"]),
        ImageSetting(
            "Gain/GainLevel", ImageSettingType.NUMBER, min_value=0, max_value=100
        ),
    ]
    mock_image_settings.get_image_values.return_value = {
        "Scene/mode": "auto",
        "Gain/GainLevel": "50",
    }
    await setup_integration(hass, mock_config_entry)

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    settings = result["image_settings"]["settings"]
    assert settings["Scene/mode"]["known"] is False
    assert settings["Gain/GainLevel"]["known"] is True


@pytest.mark.usefixtures("mock_hikcamera")
async def test_diagnostics_without_image_settings(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test a camera without image settings reports none."""
    await setup_integration(hass, mock_config_entry)

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert result["image_settings"] is None
    assert result["device_type"]


@pytest.mark.usefixtures("mock_hikcamera")
async def test_raw_documents_are_reported_as_sent(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    raw_documents: dict[str, str],
) -> None:
    """Test the camera's own documents are included, for bug reports and tests."""
    await setup_integration(hass, mock_config_entry)

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert result["image_settings"]["raw_documents"] == {
        "capabilities": raw_documents[CAPABILITIES],
        "values": raw_documents[VALUES],
    }
    assert {call.args for call in mock_image_settings.request_raw.call_args_list} == {
        ("GET", CAPABILITIES),
        ("GET", VALUES),
    }


@pytest.mark.usefixtures("mock_hikcamera")
@pytest.mark.parametrize(
    ("response", "expected"),
    [
        pytest.param(
            RawResponse(404, b"<ResponseStatus/>"), "error: HTTP 404", id="http_error"
        ),
        pytest.param(
            ISAPIConnectionError("Timeout connecting to 192.0.2.1"),
            "error: ISAPIConnectionError",
            id="connection_error",
        ),
    ],
)
async def test_unreadable_raw_documents(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    response: RawResponse | Exception,
    expected: str,
) -> None:
    """Test a document that cannot be read is reported as such."""
    mock_image_settings.request_raw.side_effect = [response, response]
    await setup_integration(hass, mock_config_entry)

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert result["image_settings"]["raw_documents"] == {
        "capabilities": expected,
        "values": expected,
    }
    # The address from the error text is not in the diagnostics.
    assert "192.0.2.1" not in str(result)


@pytest.mark.usefixtures("mock_hikcamera")
async def test_raw_documents_are_not_read_with_a_rejected_password(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test the diagnostics do not send a password the camera already rejected."""
    await setup_integration(hass, mock_config_entry)
    mock_config_entry.runtime_data.image_coordinators[0].credentials_rejected = True

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    mock_image_settings.request_raw.assert_not_called()
    assert result["image_settings"]["raw_documents"] == {
        "capabilities": "error: credentials rejected",
        "values": "error: credentials rejected",
    }


async def test_a_rejected_password_stops_reading_raw_documents(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_hikcamera: MagicMock,
    mock_image_settings: MagicMock,
) -> None:
    """Test the second document is not asked for with a password just rejected.

    The stream is stopped and new credentials are asked for, as after a write.
    """
    mock_image_settings.request_raw.side_effect = [RawResponse(401, b"")]
    await setup_integration(hass, mock_config_entry)

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert mock_image_settings.request_raw.call_count == 1
    assert result["image_settings"]["raw_documents"] == {
        "capabilities": "error: HTTP 401",
        "values": "error: HTTP 401",
    }
    # The rejection is dealt with as for any other request.
    await hass.async_block_till_done(wait_background_tasks=True)
    assert mock_config_entry.runtime_data.image_coordinators[0].credentials_rejected
    mock_hikcamera.return_value.disconnect.assert_called_once()
    flows = hass.config_entries.flow.async_progress()
    assert len(flows) == 1
    assert flows[0]["context"]["source"] == SOURCE_REAUTH


@pytest.mark.usefixtures("mock_hikcamera")
async def test_a_password_the_stream_rejects_meanwhile_is_not_sent_again(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
    raw_documents: dict[str, str],
) -> None:
    """Test the second document is not asked for once the stream had it rejected.

    The rejection comes while the first document is read.
    """
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators

    def _rejected_meanwhile(method: str, endpoint: str) -> RawResponse:
        coordinator.credentials_rejected = True
        return RawResponse(200, raw_documents[endpoint].encode())

    mock_image_settings.request_raw.side_effect = _rejected_meanwhile

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    mock_image_settings.request_raw.assert_called_once_with("GET", CAPABILITIES)
    assert result["image_settings"]["raw_documents"] == {
        "capabilities": raw_documents[CAPABILITIES],
        "values": "error: credentials rejected",
    }


@pytest.mark.usefixtures("mock_hikcamera")
async def test_raw_documents_are_not_read_while_home_assistant_stops(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test no request is sent once this client is closing.

    Called directly: the HTTP API refuses requests while Home Assistant stops.
    """
    await setup_integration(hass, mock_config_entry)

    hass.set_state(CoreState.stopping)
    result = await async_get_config_entry_diagnostics(hass, mock_config_entry)
    hass.set_state(CoreState.running)

    mock_image_settings.request_raw.assert_not_called()
    assert result["image_settings"]["raw_documents"] == {
        "capabilities": "error: the image settings client is closing",
        "values": "error: the image settings client is closing",
    }


@pytest.mark.usefixtures("mock_hikcamera")
async def test_a_cancelled_download_keeps_the_client_until_the_request_ends(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test the lock stays held until the raw read ends, though the download stops.

    Another request would otherwise overlap it on the same client.
    """
    await setup_integration(hass, mock_config_entry)
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    started = threading.Event()
    finish = threading.Event()

    def _slow_read(method: str, endpoint: str) -> RawResponse:
        started.set()
        finish.wait(5)
        return RawResponse(200, b"<ImageChannel/>")

    mock_image_settings.request_raw.side_effect = _slow_read
    download = hass.async_create_task(
        async_get_config_entry_diagnostics(hass, mock_config_entry)
    )
    await hass.async_add_executor_job(started.wait, 5)

    download.cancel()
    for _ in range(10):
        await asyncio.sleep(0)
    assert coordinator.lock.locked()
    assert not download.done()

    finish.set()
    with pytest.raises(asyncio.CancelledError):
        await download
    assert not coordinator.lock.locked()


@pytest.mark.usefixtures("raw_documents", "mock_hikcamera")
async def test_the_flag_of_a_linked_mode_is_not_an_unknown_value(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test a value that a discovered setting covers is not reported as unknown.

    pyHik folds the enabled flag of a mode into the mode's setting. The camera may
    also spell a path in another case in its values.
    """
    mock_image_settings.get_image_settings.return_value = [
        ImageSetting(
            "BLC/BLCMode",
            ImageSettingType.SELECT,
            options=["CLOSE", "UP"],
            value="UP",
            linked_enabled_path="BLC/enabled",
            off_value="CLOSE",
        ),
    ]
    mock_image_settings.get_image_values.return_value = {
        "BLC/BLCMode": "UP",
        "BLC/enabled": "true",
        "blc/blcMode": "UP",
        "Color/brightnessLevel": "50",
    }
    await setup_integration(hass, mock_config_entry)

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert result["image_settings"]["other_values"] == {"Color/brightnessLevel": "50"}
    assert (
        result["image_settings"]["settings"]["BLC/BLCMode"]["linked_enabled_path"]
        == "BLC/enabled"
    )


@pytest.mark.usefixtures("raw_documents", "mock_hikcamera")
async def test_a_range_json_cannot_hold_is_reported_as_text(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test the ends of a range that are not numbers do not break the download.

    The number platform skips such a setting, but it stays a discovered setting.
    """
    mock_image_settings.get_image_settings.return_value = [
        ImageSetting(
            "Color/brightnessLevel",
            ImageSettingType.NUMBER,
            min_value=math.nan,
            max_value=math.inf,
            value="50",
        ),
        ImageSetting(
            "Color/contrastLevel",
            ImageSettingType.NUMBER,
            min_value=-math.inf,
            max_value=100,
            value="50",
        ),
    ]
    mock_image_settings.get_image_values.return_value = {
        "Color/brightnessLevel": "50",
        "Color/contrastLevel": "50",
    }
    await setup_integration(hass, mock_config_entry)

    # Read through the HTTP API, which would refuse to send NaN or Infinity.
    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    settings = result["image_settings"]["settings"]
    assert (
        settings["Color/brightnessLevel"]["min"],
        settings["Color/brightnessLevel"]["max"],
    ) == ("nan", "inf")
    assert (
        settings["Color/contrastLevel"]["min"],
        settings["Color/contrastLevel"]["max"],
    ) == ("-inf", 100)
    assert "NaN" not in json.dumps(result, allow_nan=False)


@pytest.mark.usefixtures("raw_documents", "mock_hikcamera")
async def test_a_value_spelled_otherwise_is_shown_with_its_setting(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test a value the camera spells in another case is found for its setting."""
    mock_image_settings.get_image_settings.return_value = [
        ImageSetting(
            "BLC/BLCMode",
            ImageSettingType.SELECT,
            options=["CLOSE", "UP"],
            value="UP",
        ),
    ]
    mock_image_settings.get_image_values.return_value = {"blc/blcMode": "UP"}
    await setup_integration(hass, mock_config_entry)

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert result["image_settings"]["settings"]["BLC/BLCMode"]["value"] == "UP"
    assert result["image_settings"]["other_values"] == {}


@pytest.mark.usefixtures("mock_hikcamera", "mock_image_settings")
async def test_diagnostics_of_an_unloaded_entry(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
) -> None:
    """Test an entry without runtime data still gives the entry and the version."""
    await setup_integration(hass, mock_config_entry)
    assert await hass.config_entries.async_unload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert result["entry"]["data"]["password"] == "**REDACTED**"
    assert result["pyhik_version"] == pyhik.__version__
    assert result["device_type"] is None
    assert result["channels"] == []
    assert result["image_settings"] is None


@pytest.mark.usefixtures("raw_documents", "mock_hikcamera")
async def test_current_values_are_read_from_the_camera(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test the values are read when the diagnostics are built, not taken cached.

    The coordinator does not poll when no entity listens, as when they are all
    disabled, so its cached values can be old.
    """
    mock_image_settings.get_image_settings.return_value = [
        ImageSetting(
            "Gain/GainLevel", ImageSettingType.NUMBER, min_value=0, max_value=100
        ),
    ]
    mock_image_settings.get_image_values.return_value = {"Gain/GainLevel": "50"}
    await setup_integration(hass, mock_config_entry)
    mock_image_settings.get_image_values.return_value = {"gain/gainLevel": "70"}

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert result["image_settings"]["values_source"] == "camera"
    assert result["image_settings"]["settings"]["Gain/GainLevel"]["value"] == "70"
    assert result["image_settings"]["other_values"] == {}
    # Only the diagnostics got the new values.
    [coordinator] = mock_config_entry.runtime_data.image_coordinators
    assert coordinator.data == {"Gain/GainLevel": "50"}


@pytest.mark.usefixtures("raw_documents", "mock_hikcamera")
async def test_cached_values_are_reported_if_the_camera_cannot_be_read(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test the last values read are reported when the camera does not answer."""
    mock_image_settings.get_image_settings.return_value = [
        ImageSetting(
            "Gain/GainLevel", ImageSettingType.NUMBER, min_value=0, max_value=100
        ),
    ]
    mock_image_settings.get_image_values.return_value = {"Gain/GainLevel": "50"}
    await setup_integration(hass, mock_config_entry)
    mock_image_settings.get_image_values.side_effect = ISAPIConnectionError("Timeout")

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert result["image_settings"]["values_source"] == "cached"
    assert result["image_settings"]["settings"]["Gain/GainLevel"]["value"] == "50"
