"""HA entity service."""

from collections.abc import Sequence
import uuid

import domika_ha_framework.subscription.service as subscription_service
from domika_ha_framework.utils import flatten_json
from sqlalchemy.ext.asyncio import AsyncSession

from homeassistant.core import async_get_hass

from ..const import LOGGER
from .models import DomikaHaEntity


async def get(
    db_session: AsyncSession,
    app_session_id: uuid.UUID,
    *,
    need_push: bool | None = True,
    entity_id: str | None = None,
) -> Sequence[DomikaHaEntity]:
    """Get the attribute state of all entities from the subscription for the given app_session_id."""
    result: list[DomikaHaEntity] = []

    entities_attributes: dict[str, list[str]] = {}

    subscriptions = await subscription_service.get(
        db_session,
        app_session_id,
        need_push=need_push,
        entity_id=entity_id,
    )

    # Convolve entities attribute in for of dict:
    # { noqa: ERA001
    #   "entity_id": ["attr1", "attr2"]
    # } noqa: ERA001
    for subscription in subscriptions:
        entities_attributes.setdefault(subscription.entity_id, []).append(
            subscription.attribute
        )

    hass = async_get_hass()
    for entity, attributes in entities_attributes.items():
        state = hass.states.get(entity)
        if state:
            flat_state = flatten_json(
                state.as_compressed_state,
                exclude={"c", "lc", "lu"},
            )
            filtered_dict = {k: v for (k, v) in flat_state.items() if k in attributes}
            domika_entity = DomikaHaEntity(
                entity_id=entity,
                time_updated=max(state.last_changed, state.last_updated).timestamp(),
                attributes=filtered_dict,
            )
            result.append(
                domika_entity,
            )
        else:
            LOGGER.error(
                'Ha_entity.get is requesting state of unknown entity: "%s"',
                entity,
            )

    return result
