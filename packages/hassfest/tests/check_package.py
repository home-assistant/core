"""Exercise the installed shared hassfest package outside the checkout."""

from importlib.metadata import version
from importlib.resources import files
from importlib.util import find_spec
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from hassfest.model import Config
from hassfest.plugins import INTEGRATION_PLUGINS, load_plugins
from hassfest.runner import run
from hassfest.serializer import format_python_namespace


def main() -> None:
    """Check the installed artifact and runner with the shared validators."""
    assert find_spec("homeassistant") is None
    data = files("hassfest") / "_data"
    assert json.loads((data / "build.json").read_text())["version"] == version(
        "hassfest"
    )
    assert "EXAMPLE = True" in format_python_namespace({"EXAMPLE": True})

    with TemporaryDirectory() as directory:
        root = Path(directory)
        integration = root / "custom_components/hassfest_example"
        integration.mkdir(parents=True)
        manifest = {
            "domain": "hassfest_example",
            "name": "Hassfest Example",
            "codeowners": ["@home-assistant/core"],
        }
        manifest_path = integration / "manifest.json"
        manifest_path.write_text(json.dumps(manifest))
        config = Config(
            root=root,
            specific_integrations=[integration],
            action="validate",
            requirements=False,
            plugins=set(INTEGRATION_PLUGINS),
        )
        plugins = load_plugins(config)
        assert run(config, plugins) == 0

        # Leave invalid field types for the manifest validator to report.
        manifest["codeowners"] = None
        manifest_path.write_text(json.dumps(manifest))
        assert run(config, plugins) == 0

        manifest["codeowners"] = ["invalid-owner"]
        manifest_path.write_text(json.dumps(manifest))
        assert run(config, plugins) == 1

        manifest["codeowners"] = ["@home-assistant/core"]
        manifest_path.write_text(json.dumps(manifest))
        (integration / "invalid.json").write_text("{")
        assert run(config, plugins) == 1

    assert not any(
        name == "script" or name.startswith("script.") for name in sys.modules
    )
    print("Installed hassfest shared validators and runner work outside the checkout")


if __name__ == "__main__":
    main()
