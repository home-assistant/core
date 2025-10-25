"""Helper functions for Zero Grid integration."""


def parse_entity_domain(entity_id: str) -> str:
    """Extract the domain from an entity ID.

    Args:
        entity_id: The entity ID (e.g., 'switch.my_switch')

    Returns:
        The domain portion of the entity ID (e.g., 'switch')
    """
    return entity_id.split(".")[0]
