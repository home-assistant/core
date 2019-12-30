"""Helpers to handle IDs."""
from typing import Any, Dict, List

from homeassistant.util import slugify


class IDManager:
    """Keep track of IDs across different collections."""

    def __init__(self) -> None:
        """Initiate the ID manager."""
        self.collections: List[Dict[str, Any]] = []

    def add_collection(self, collection: Dict[str, Any]) -> None:
        """Add a collection to check for ID usage."""
        self.collections.append(collection)

    def has_id(self, item_id: str) -> bool:
        """Test if the ID exists."""
        return any(item_id in collection for collection in self.collections)

    def generate_id(self, suggestion: str) -> str:
        """Generate an ID."""
        base = slugify(suggestion)
        proposal = base
        attempt = 1

        while self.has_id(proposal):
            attempt += 1
            proposal = f"{base}_{attempt}"

        return proposal
