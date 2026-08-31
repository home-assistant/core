"""Test KNX Information Model semantics constants."""

from homeassistant.components.knx.const import SUPPORTED_PLATFORMS_UI
from homeassistant.components.knx.storage.dpa import FUNCTIONAL_BLOCK_PLATFORMS
from homeassistant.components.knx.storage.entity_suggestions.functional_blocks import (
    _collect_dpa_index,
)


def test_functional_block_platform_map() -> None:
    """Test FUNCTIONAL_BLOCK_PLATFORMS mapping consistency with schema annotations."""
    dpas_of_platform = {
        platform: set(_collect_dpa_index(platform))
        for platform in SUPPORTED_PLATFORMS_UI
    }
    for functional_block, platforms in FUNCTIONAL_BLOCK_PLATFORMS.items():
        for platform in platforms:
            assert platform in SUPPORTED_PLATFORMS_UI
            # every mapped platform shall have at least one DPA
            # annotation of that functional block in its schema
            assert any(
                dpa.startswith(f"{functional_block}.")
                for dpa in dpas_of_platform[platform]
            ), f"No DPA of FB {functional_block} in {platform} schema"

    # every DPA annotation shall have its functional block
    # registered in FUNCTIONAL_BLOCK_PLATFORMS for that platform
    for platform, dpas in dpas_of_platform.items():
        for dpa in dpas:
            functional_block = dpa.split(".")[0]
            assert platform in FUNCTIONAL_BLOCK_PLATFORMS.get(functional_block, []), (
                f"DPA {dpa} in {platform} schema but FB {functional_block}"
                " not mapped to that platform in FUNCTIONAL_BLOCK_PLATFORMS"
            )
    # DPA format sanity check: "<fb>.<datapoint>" - both numeric
    for dpas in dpas_of_platform.values():
        for dpa in dpas:
            fb_part, dpa_part = dpa.split(".")
            assert fb_part.isdigit() and dpa_part.isdigit()
