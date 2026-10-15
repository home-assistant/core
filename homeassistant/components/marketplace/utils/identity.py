"""Tell repositories apart when GitHub gave one of them a new id."""

from typing import Any


def _id_order(repository_id: str) -> int:
    """Return an id to compare by, GitHub hands out ids in increasing order."""
    return int(repository_id) if repository_id.isdigit() else -1


def newest_id_per_name(
    repositories: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Keep one entry per repository name, the one with the newest id.

    A repository deleted and created again on GitHub can show up under both.
    """
    newest: dict[str, tuple[str, dict[str, Any]]] = {}
    for repository_id, repository_data in repositories.items():
        name = repository_data["full_name"].lower()
        if name not in newest or _id_order(repository_id) > _id_order(newest[name][0]):
            newest[name] = (repository_id, repository_data)

    return dict(newest.values())


def one_stored_entry_per_name(
    repositories: dict[str, dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    """Keep one stored entry per repository name.

    Stored data can hold a repository under an old and a new id. The entry that
    was installed is the one that matters, otherwise the newest id.
    """
    kept: dict[str, tuple[str, dict[str, Any]]] = {}
    for repository_id, repository_data in repositories.items():
        if not (full_name := repository_data.get("full_name")):
            kept[repository_id] = (repository_id, repository_data)
            continue

        name = full_name.lower()
        if name not in kept or _preference(repository_id, repository_data) > (
            _preference(*kept[name])
        ):
            kept[name] = (repository_id, repository_data)

    return dict(kept.values())


def _preference(
    repository_id: str, repository_data: dict[str, Any]
) -> tuple[bool, int]:
    """Return how much a stored entry is worth keeping."""
    return bool(repository_data.get("installed")), _id_order(repository_id)
