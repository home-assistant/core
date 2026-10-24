"""Package metadata validation and generation."""

import json
import tomllib
from typing import Any

from homeassistant.const import REQUIRED_PYTHON_VER, __version__

from .model import Config, Integration

CODEMETA_PATH = "codemeta.json"

_URL_MAP: dict[str, str] = {
    "homepage": "url",
    "source code": "codeRepository",
    "bug reports": "issueTracker",
    "docs: dev": "softwareHelp",
    "documentation": "softwareHelp",
}

_ORG_INDICATORS: tuple[str, ...] = ("Authors", "Team", "Foundation", "Organization")


def _format_license(license_entry: str | dict[str, Any]) -> str:
    """Format license value into an SPDX URL or string."""
    text = (
        license_entry.get("text", "")
        if isinstance(license_entry, dict)
        else str(license_entry)
    )
    return (
        text
        if text.startswith(("http://", "https://"))
        else f"https://spdx.org/licenses/{text}"
    )


def _format_author(author: dict[str, str]) -> dict[str, str]:
    """Format author entry into CodeMeta schema structure."""
    name = author.get("name", "")
    author_type = (
        "Organization" if any(w in name for w in _ORG_INDICATORS) else "Person"
    )
    entry: dict[str, str] = {"@type": author_type}
    if name:
        entry["name"] = name
    if "email" in author:
        entry["email"] = author["email"]
    return entry


def _parse_classifiers(classifiers: list[str]) -> dict[str, Any]:
    """Parse PEP 621 classifiers into CodeMeta properties."""
    programming_languages: list[str] = []
    operating_systems: list[str] = []
    audiences: list[str] = []
    app_category: str | None = None
    dev_status: str | None = None

    for item in classifiers:
        parts = [part.strip() for part in item.split("::")]
        match parts[0]:
            case "Programming Language":
                if parts[1] == "Python":
                    programming_languages.append("Python")
            case "Operating System":
                operating_systems.append(parts[1])
            case "Intended Audience":
                audiences.append(parts[1])
            case "Topic":
                app_category = parts[1]
            case "Development Status":
                dev_status = parts[1].split(" - ", 1)[-1]

    result: dict[str, Any] = {}
    if programming_languages:
        result["programmingLanguage"] = sorted(set(programming_languages))
    if operating_systems:
        result["operatingSystem"] = sorted(set(operating_systems))
    if audiences:
        result["audience"] = sorted(set(audiences))
    if app_category:
        result["applicationCategory"] = app_category
    if dev_status:
        result["developmentStatus"] = dev_status

    return result


def _generate_codemeta(data: dict[str, Any]) -> str:
    """Generate CodeMeta JSON metadata from pyproject.toml data."""
    project = data.get("project", {})

    codemeta: dict[str, Any] = {
        "@context": "https://doi.org/10.5063/schema/codemeta-2.0",
        "@type": "SoftwareSourceCode",
    }

    if name := project.get("name"):
        codemeta["identifier"] = name
        codemeta["name"] = name

    if description := project.get("description"):
        codemeta["description"] = description

    if version := project.get("version"):
        codemeta["version"] = version

    if license_entry := project.get("license"):
        codemeta["license"] = _format_license(license_entry)

    if readme := project.get("readme"):
        codemeta["readme"] = readme

    if authors := project.get("authors"):
        codemeta["author"] = [_format_author(author) for author in authors]

    if keywords := project.get("keywords"):
        codemeta["keywords"] = sorted(keywords)

    if requires_python := project.get("requires-python"):
        codemeta["runtimePlatform"] = [f"Python {requires_python}"]

    if classifiers := project.get("classifiers"):
        codemeta.update(_parse_classifiers(classifiers))

    urls = project.get("urls", {})
    related_links: list[str] = []
    for label, url in urls.items():
        if mapped_key := _URL_MAP.get(label.lower()):
            codemeta[mapped_key] = url
        else:
            related_links.append(url)

    if related_links:
        codemeta["relatedLink"] = sorted(related_links)

    sorted_meta = {k: codemeta[k] for k in sorted(codemeta)}
    return json.dumps(sorted_meta, indent=2)


def validate(integrations: dict[str, Integration], config: Config) -> None:
    """Validate project metadata keys and codemeta.json."""
    metadata_path = config.root / "pyproject.toml"
    data = tomllib.loads(metadata_path.read_text())

    try:
        if data["project"]["version"] != __version__:
            config.add_error(
                "metadata", f"'project.version' value does not match '{__version__}'"
            )
    except KeyError:
        config.add_error("metadata", "No 'metadata.version' key found!")

    required_py_version = f">={'.'.join(map(str, REQUIRED_PYTHON_VER))}"
    try:
        if data["project"]["requires-python"] != required_py_version:
            config.add_error(
                "metadata",
                "'project.requires-python' value doesn't"
                f" match '{required_py_version}'",
            )
    except KeyError:
        config.add_error("metadata", "No 'options.python_requires' key found!")

    codemeta_path = config.root / CODEMETA_PATH
    config.cache["codemeta"] = content = _generate_codemeta(data)

    if not codemeta_path.is_file() or codemeta_path.read_text() != f"{content}\n":
        config.add_error(
            "metadata",
            "File codemeta.json is not up to date. Run python3 -m script.hassfest",
            fixable=True,
        )


def generate(integrations: dict[str, Integration], config: Config) -> None:
    """Generate codemeta.json."""
    if "codemeta" not in config.cache:
        metadata_path = config.root / "pyproject.toml"
        data = tomllib.loads(metadata_path.read_text())
        config.cache["codemeta"] = _generate_codemeta(data)

    codemeta_path = config.root / CODEMETA_PATH
    codemeta_path.write_text(f"{config.cache['codemeta']}\n")
