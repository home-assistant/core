"""Tests for the official HAP-python recording API integration."""

from types import SimpleNamespace

from pyhap import hksv_recording as hk
from pyhap.loader import get_loader
import pytest

from homeassistant.components.homekit.hksv_hap import (
    RecordingCapabilities,
    make_services,
    parse_selected,
)


def test_selected_recording_uses_official_codec_and_limits() -> None:
    """Only a selection matching the advertised profiles is accepted."""
    caps = RecordingCapabilities(
        audio_codec=0,
        audio_sample_rate=2,
        resolutions=((1280, 720, 15),),
        profiles=(0, 1, 2),
        levels=(2,),
    )
    selection = hk.SelectedRecordingConfiguration(
        recording=hk.SupportedRecordingConfiguration(),
        video=hk.VideoCodecConfiguration(
            hk.VideoCodecType.H264,
            1,
            2,
            2000,
            4000,
            [hk.VideoAttributes(1280, 720, 15)],
        ),
        audio=hk.AudioCodecConfiguration(sample_rate=hk.AudioSampleRate.KHZ_24),
    )
    assert parse_selected(selection.encode(), caps)["width"] == 1280
    selection.video.attributes[0].width = 4096
    with pytest.raises(ValueError):
        parse_selected(selection.encode(), caps)


def test_service_uuids_preserve_existing_iid_keys() -> None:
    """The catalog exposes the service and characteristic UUIDs used before migration."""
    caps = RecordingCapabilities(
        audio_codec=0,
        audio_sample_rate=2,
        resolutions=((1280, 720, 15),),
        profiles=(0, 1, 2),
        levels=(2,),
    )
    services = make_services(SimpleNamespace(loader=get_loader()), caps)
    assert [
        str(service.type_id)[:8]
        for service in (services.recording, services.operating, services.transport)
    ] == ["00000204", "0000021a", "00000129"]
    assert [
        [str(char.type_id)[:8] for char in service.characteristics]
        for service in (services.recording, services.operating, services.transport)
    ] == [
        ["000000b0", "00000226", "00000209", "00000205", "00000206", "00000207"],
        ["0000021b", "00000223", "00000225"],
        ["00000131", "00000130", "00000037"],
    ]
