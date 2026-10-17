"""Exercise installed hassfest and Home Assistant wheels outside the checkout."""

from importlib.metadata import requires, version
import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory


def main() -> None:
    """Check the installed artifact, including reference data and plugin loading."""
    assert f"homeassistant=={version('homeassistant')}" in requires("hassfest")
    assert version("hassfest") == version("homeassistant")

    with TemporaryDirectory() as directory:
        root = Path(directory)
        integration = root / "custom_components/hassfest_example"
        integration.mkdir(parents=True)
        (integration / "__init__.py").write_text('"""Example integration."""\n')
        manifest = {
            "domain": "hassfest_example",
            "name": "Hassfest Example",
            "codeowners": ["@home-assistant/core"],
            "documentation": "https://example.com",
            "iot_class": "local_polling",
            "version": "1.0.0",
        }
        manifest_path = integration / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))
        command = [
            sys.executable,
            "-c",
            "import sys; from hassfest.__main__ import main; result = main(); "
            "assert not any(name == 'script' or name.startswith('script.') for name in sys.modules); "
            "sys.exit(result)",
            "--integration-path",
            str(integration),
            "--requirements",
        ]
        result = subprocess.run(
            command, cwd=root, capture_output=True, text=True, check=False
        )
        assert result.returncode == 0, result.stdout + result.stderr
        assert "Invalid integrations: 0" in result.stdout

        # This is an HA dependency, so bundled requirements must reject it even
        # though the current directory contains no requirements or Core files.
        manifest["requirements"] = ["aiohttp==0.0.0"]
        manifest_path.write_text(json.dumps(manifest))
        result = subprocess.run(
            command, cwd=root, capture_output=True, text=True, check=False
        )
        assert result.returncode == 1, result.stdout + result.stderr
        assert "is a dependency of Home Assistant itself" in result.stdout

        manifest["requirements"] = ["aioshelly==0.0.0"]
        manifest_path.write_text(json.dumps(manifest))
        result = subprocess.run(
            command, cwd=root, capture_output=True, text=True, check=False
        )
        assert result.returncode == 1, result.stdout + result.stderr
        assert "is incompatible with aioshelly" in result.stdout

        # Category lookup must use the installed HA data, not silently skip it.
        del manifest["requirements"]
        manifest["categories"] = ["nonexistent_category"]
        manifest_path.write_text(json.dumps(manifest))
        result = subprocess.run(
            command, cwd=root, capture_output=True, text=True, check=False
        )
        assert result.returncode == 1, result.stdout + result.stderr
        assert "Unknown category `nonexistent_category`" in result.stdout

    print("Installed hassfest validates integrations using packaged HA data")


if __name__ == "__main__":
    main()
