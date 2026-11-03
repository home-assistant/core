"""Functional hardware selection and safe fallback tests."""

from unittest.mock import AsyncMock, patch

import pytest

from homeassistant.components.homekit.hksv_hardware import (
    HardwareEncoder,
    HardwareEncoderProbe,
    _candidates,
    _matches_sps,
)

SPS_BASELINE_31 = b"\x00\x00\x00\x01\x67\x42\xc0\x1f\x80"


def test_sps_profile_and_level_are_checked() -> None:
    """A lower H264 level is accepted; wrong profile and higher level fail."""
    assert _matches_sps(SPS_BASELINE_31, 66, 32)
    assert not _matches_sps(SPS_BASELINE_31, 77, 32)
    assert not _matches_sps(SPS_BASELINE_31, 66, 30)
    assert not _matches_sps(b"", 66, 31)
    assert not _matches_sps(b"\x00\x00\x01\x67\x42\x00\x1f", 66, 31)


async def test_probing_cache_and_invalidation() -> None:
    """A verified encoder is cached, then retried after invalidation."""
    probe = HardwareEncoderProbe()
    candidate = HardwareEncoder("h264_nvenc", (), "format=nv12", ())
    with (
        patch(
            "homeassistant.components.homekit.hksv_hardware._candidates",
            return_value=(candidate,),
        ),
        patch.object(probe, "_test", new_callable=AsyncMock, return_value=True) as test,
    ):
        assert await probe.select("ffmpeg", 0, 0, 1280, 720, 15) == candidate
        assert await probe.select("ffmpeg", 0, 0, 1280, 720, 15) == candidate
        assert test.await_count == 1
        probe.invalidate()
        assert await probe.select("ffmpeg", 0, 0, 1280, 720, 15) == candidate
        assert test.await_count == 2


async def test_probe_falls_back_for_unavailable_or_invalid() -> None:
    """No usable device and invalid parameters choose software."""
    probe = HardwareEncoderProbe()
    with (
        patch(
            "homeassistant.components.homekit.hksv_hardware._candidates",
            return_value=(HardwareEncoder("h264_nvenc", (), "format=nv12", ()),),
        ),
        patch.object(
            probe, "_test", new_callable=AsyncMock, return_value=False
        ) as test,
    ):
        assert await probe.select("ffmpeg", 0, 0, 1280, 720, 15) is None
        assert test.await_count >= 1
        assert await probe.select("ffmpeg", 7, 0, 1280, 720, 15) is None


@pytest.mark.parametrize(
    ("output", "expected"), [(SPS_BASELINE_31, True), (b"bad", False)]
)
async def test_probe_checks_real_output(output: bytes, expected: bool) -> None:
    """An encoder listing or success code alone cannot authorize selection."""
    process = AsyncMock()
    process.communicate.return_value = (output, b"")
    process.returncode = 0
    probe = HardwareEncoderProbe()
    candidate = HardwareEncoder("h264_nvenc", (), "format=nv12", ())
    with patch(
        "asyncio.create_subprocess_exec", new_callable=AsyncMock, return_value=process
    ):
        assert await probe._test("ffmpeg", candidate, 640, 360, 15, 66, 31) is expected


async def test_report_failure_temporarily_disables_codec() -> None:
    """A runtime failure does not cause an immediate hardware retry."""
    probe = HardwareEncoderProbe()
    candidate = HardwareEncoder("h264_nvenc", (), "format=nv12", ())
    with (
        patch(
            "homeassistant.components.homekit.hksv_hardware._candidates",
            return_value=(candidate,),
        ),
        patch.object(probe, "_test", new_callable=AsyncMock, return_value=True) as test,
    ):
        assert await probe.select("ffmpeg", 0, 0, 640, 360, 15) == candidate
        probe.report_failure(candidate.codec)
        assert await probe.select("ffmpeg", 0, 0, 640, 360, 15) is None
        assert test.await_count == 1
        with patch(
            "homeassistant.components.homekit.hksv_hardware.time.monotonic",
            return_value=10**12,
        ):
            assert await probe.select("ffmpeg", 0, 0, 640, 360, 15) == candidate
        assert test.await_count == 2


async def test_probe_with_real_ffmpeg_encoder() -> None:
    """A real bounded synthetic encode must emit a matching H.264 SPS."""
    import shutil  # noqa: PLC0415

    if not (ffmpeg := shutil.which("ffmpeg")):
        pytest.skip("ffmpeg unavailable")
    candidate = HardwareEncoder(
        "libx264", (), "format=nv12", ("-profile:v", "baseline", "-level:v", "3.1")
    )
    assert await HardwareEncoderProbe()._test(ffmpeg, candidate, 640, 360, 15, 66, 31)


def test_no_nvidia_device_skips_nvenc() -> None:
    """Do not try NVENC when no NVIDIA device exists."""
    with patch("homeassistant.components.homekit.hksv_hardware.glob", return_value=[]):
        assert _candidates("baseline", "3.1") == ()


async def test_negative_result_expires() -> None:
    """A newly attached GPU can be discovered after five minutes."""
    probe = HardwareEncoderProbe()
    candidate = HardwareEncoder("h264_nvenc", (), "format=nv12", ())
    with (
        patch(
            "homeassistant.components.homekit.hksv_hardware._candidates",
            return_value=(candidate,),
        ),
        patch(
            "homeassistant.components.homekit.hksv_hardware.time.monotonic",
            return_value=100,
        ) as clock,
        patch.object(
            probe, "_test", new_callable=AsyncMock, side_effect=[False, True]
        ) as test,
    ):
        assert await probe.select("ffmpeg", 0, 0, 640, 360, 15) is None
        clock.return_value = 399
        assert await probe.select("ffmpeg", 0, 0, 640, 360, 15) is None
        assert test.await_count == 1
        clock.return_value = 401
        assert await probe.select("ffmpeg", 0, 0, 640, 360, 15) == candidate
        assert test.await_count == 2
