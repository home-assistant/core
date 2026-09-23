"""Tests that the store carries no names of the custom integration it replaces."""

from pathlib import Path

import homeassistant.components.store as store_integration

INTEGRATION_PATH = Path(store_integration.__file__).parent

# Every mention of HACS left in the integration has to carry one of these.
ALLOWED_TOKENS: dict[str, str] = {
    "hacs.json": "the manifest file name repositories ship",
    "hacs/default": "the catalog repository",
    "hacs/integration": "the repository of the custom integration",
    "data-v2.hacs.xyz": "the catalog feed",
    "hacs_repository": "the my.home-assistant.io redirect slug",
    "hacs.hacs": "legacy storage key",
    "hacs.repositories": "legacy storage key",
    "hacs.critical": "legacy storage key",
    "hacs.data": "legacy storage key",
    "custom_components/hacs": "where the custom integration was installed",
    "LEGACY_HACS_": "constants that name what the custom integration left behind",
    "hacs.xyz": "documentation links",
    "/hacsfiles": "the path the custom integration served dashboard resources from",
}

# Tokens that are only allowed in a single file.
ALLOWED_TOKENS_IN_FILE: dict[str, dict[str, str]] = {
    "__init__.py": {
        "/hacs": "the panel path of the custom integration, redirected to the store",
    },
    "const.py": {
        '"hacs"': "the domain of the custom integration",
    },
    "migration.py": {
        '"hacs"': "the domain of the custom integration",
        '"hacstag"': "the query parameter on migrated dashboard resource URLs",
    },
    "repositories/base.py": {
        '"hacs-default",': "a GitHub topic filtered from repository topics",
        '"hacs-integration",': "a GitHub topic filtered from repository topics",
        '"hacs-repository",': "a GitHub topic filtered from repository topics",
        '"hacs",': "a GitHub topic filtered from repository topics",
        '"home-assistant-hacs",': "a GitHub topic filtered from repository topics",
    },
    "utils/validate.py": {
        'vol.Optional("hacs")': "the minimum version key of the repository manifest",
    },
}


def _leftovers(path: Path) -> list[str]:
    """Return the lines of a file that mention HACS without an allowed token."""
    relative = path.relative_to(INTEGRATION_PATH).as_posix()
    allowed = (*ALLOWED_TOKENS, *ALLOWED_TOKENS_IN_FILE.get(relative, {}))

    return [
        f"{relative}:{number}: {line.strip()}"
        for number, line in enumerate(
            path.read_text(encoding="utf-8").splitlines(), start=1
        )
        if "hacs" in line.lower() and not any(token in line for token in allowed)
    ]


def test_no_hacs_leftovers() -> None:
    """Test every mention of HACS in the integration is one that has to stay."""
    leftovers = [
        leftover
        for path in sorted(INTEGRATION_PATH.rglob("*"))
        if path.suffix in (".py", ".json")
        for leftover in _leftovers(path)
    ]

    assert not leftovers, "HACS leftovers found:\n" + "\n".join(leftovers)
