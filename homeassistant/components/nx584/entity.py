"""Base entity for the NX584 integration."""

from typing import override

from homeassistant.helpers.entity import Entity


class NX584Entity(Entity):
    """Entity that keeps the entity namespace of its imported YAML platform."""

    _entity_namespace: str | None = None

    @property
    @override
    def suggested_object_id(self) -> str | None:
        """Return the object ID, prefixed like the YAML platform did."""
        object_id = super().suggested_object_id
        if self._entity_namespace is None:
            return object_id
        return f"{self._entity_namespace} {object_id}"
