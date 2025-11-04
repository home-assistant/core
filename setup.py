"""Setup script for Home Assistant with Rust extensions."""

from setuptools import setup
from setuptools_rust import Binding, RustExtension

setup(
    name="homeassistant",
    rust_extensions=[
        RustExtension(
            "homeassistant.rust_core.rust_core",
            path="homeassistant/rust_core/Cargo.toml",
            binding=Binding.PyO3,
            debug=False,
        )
    ],
    # Don't zip files - it breaks the Rust extension
    zip_safe=False,
)
