"""Test Hikvision diagnostics."""

import asyncio
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
from homeassistant.core import HomeAssistant
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
        f"{TEST_DEVICE_ID}_image_scene/mode",
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
async def test_diagnostics_stop_at_the_first_rejection(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test a refused request is not followed by another, and asks for a password."""
    # The client returns the status of a refused request instead of raising it.
    mock_image_settings.request_raw.side_effect = [RawResponse(401, b"")]
    await setup_integration(hass, mock_config_entry)

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert mock_image_settings.request_raw.call_count == 1
    assert result["image_settings"]["raw_documents"] == {
        "capabilities": "error: credentials rejected",
        "values": "error: credentials rejected",
    }
    assert mock_config_entry.runtime_data.image_credentials_rejected
    flows = hass.config_entries.flow.async_progress()
    assert [flow["context"]["source"] for flow in flows] == [SOURCE_REAUTH]


@pytest.mark.usefixtures("mock_hikcamera")
async def test_a_stopped_download_keeps_the_client_until_the_request_ends(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test a request is not left running on a client that another one can use."""
    started = threading.Event()
    release = threading.Event()

    def request_raw(method: str, endpoint: str) -> RawResponse:
        started.set()
        assert release.wait(5)
        return RawResponse(200, b"<document/>")

    # A plain function, so that it runs in a thread and blocks only itself.
    mock_image_settings.request_raw = request_raw
    await setup_integration(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data.image_coordinators[0]

    download = hass.async_create_task(
        async_get_config_entry_diagnostics(hass, mock_config_entry)
    )
    async with asyncio.timeout(5):
        while not started.is_set():
            await asyncio.sleep(0)
    download.cancel()
    with pytest.raises(asyncio.CancelledError):
        await download

    assert coordinator.lock.locked()
    release.set()
    await hass.async_block_till_done()
    assert not coordinator.lock.locked()


@pytest.mark.usefixtures("mock_hikcamera")
async def test_the_second_document_is_not_read_after_the_credentials_are_rejected(
    hass: HomeAssistant,
    hass_client: ClientSessionGenerator,
    mock_config_entry: MockConfigEntry,
    mock_image_settings: MagicMock,
) -> None:
    """Test a rejection found while the first document is read stops the download."""
    await setup_integration(hass, mock_config_entry)
    data = mock_config_entry.runtime_data

    def request_raw(method: str, endpoint: str) -> RawResponse:
        # The event stream is refused the password while this is being read.
        data.image_credentials_rejected = True
        return RawResponse(200, b"<capabilities/>")

    mock_image_settings.request_raw = MagicMock(side_effect=request_raw)

    result = await get_diagnostics_for_config_entry(
        hass, hass_client, mock_config_entry
    )

    assert mock_image_settings.request_raw.call_count == 1
    assert result["image_settings"]["raw_documents"] == {
        "capabilities": "<capabilities/>",
        "values": "error: credentials rejected",
    }
