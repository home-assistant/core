"""Test Immich Frames rendering contracts."""

from io import BytesIO

from PIL import Image

from homeassistant.components.immich_frames.rendering import image_size, render


def _jpeg(size: tuple[int, int], colour: str) -> bytes:
    """Create a small test JPEG."""
    output = BytesIO()
    Image.new("RGB", size, colour).save(output, "JPEG")
    return output.getvalue()


def test_render_exact_output_sizes() -> None:
    """Render every supported screen shape at its exact contract size."""
    payload = _jpeg((400, 300), "red")

    for shape, expected in {
        "landscape": (1280, 800),
        "portrait": (800, 1280),
        "square": (720, 720),
    }.items():
        rendered, layout = render([payload], shape, "show_full")
        assert image_size(rendered) == expected
        assert layout == "single"


def test_render_pair_uses_side_by_side_layout() -> None:
    """Render two photos into one deterministic frame."""
    rendered, layout = render(
        [_jpeg((300, 500), "red"), _jpeg((500, 300), "blue")],
        "landscape",
        "crop",
    )

    assert image_size(rendered) == (1280, 800)
    assert layout == "side_by_side"
