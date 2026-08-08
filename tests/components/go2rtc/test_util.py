"""Go2rtc utility function tests."""

from unittest.mock import Mock

import pytest

from homeassistant.components.camera import Camera
from homeassistant.components.go2rtc.util import get_camera_identifier


@pytest.mark.parametrize(
    ("unique_id", "entity_id", "expected"),
    [
        # Prefer unique_id over entity_id
        ("unique123", "camera.test", "test_unique123"),
        # Fall back to entity_id when unique_id is None
        (None, "camera.test", "camera.test"),
        # Safe characters pass through
        ("abc-def_ghi.123", "camera.test", "test_abc-def_ghi.123"),
        # Special characters are percent-encoded
        ("cam#1", "camera.test", "test_cam%231"),
        ("cam:1", "camera.test", "test_cam%3A1"),
        ("cam/1", "camera.test", "test_cam%2F1"),
        ("cam?1", "camera.test", "test_cam%3F1"),
        ("cam&1", "camera.test", "test_cam%261"),
        ("cam=1", "camera.test", "test_cam%3D1"),
        ("cam%1", "camera.test", "test_cam%251"),
        ("cam 1", "camera.test", "test_cam%201"),
        ("cam@1", "camera.test", "test_cam%401"),
        ("cam_1", "camera.test", "test_cam_1"),
        ("cam%231", "camera.test", "test_cam%25231"),
        # Non-ASCII: UTF-8 byte-wise encoding (€ = E2 82 AC)
        ("cam€1", "camera.test", "test_cam%E2%82%AC1"),
    ],
)
def test_get_camera_identifier(
    unique_id: str | None, entity_id: str, expected: str
) -> None:
    """Test get_camera_identifier sanitizes and prefers unique_id."""
    camera = Mock(spec_set=Camera)
    camera.platform.platform_name = "test"
    camera.unique_id = unique_id
    camera.entity_id = entity_id
    assert get_camera_identifier(camera) == expected
