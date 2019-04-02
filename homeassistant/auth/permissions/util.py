"""Helpers to deal with permissions."""
from functools import wraps

from typing import (  # noqa: F401
    TYPE_CHECKING, Callable, Dict, List, Optional, Union, cast)

from homeassistant.exceptions import Unauthorized, UnknownUser

from .const import POLICY_CONTROL
from .models import PermissionLookup
from .types import CategoryType, SubCategoryDict, ValueType

if TYPE_CHECKING:
    from homeassistant.core import HomeAssistant, Service, ServiceCall  # noqa

LookupFunc = Callable[[PermissionLookup, SubCategoryDict, str],
                      Optional[ValueType]]
SubCatLookupType = Dict[str, LookupFunc]


def authorized_service_call(hass: 'HomeAssistant', domain: str) -> Callable:
    """Ensure user of a config entry-enabled service call has permission."""
    def decorator(service: 'Service') -> Callable:
        """Decorate."""
        @wraps(service)
        async def check_permissions(call: 'ServiceCall') -> None:
            """Check user permission and raise before call if unauthorized."""
            if not call.context.user_id:
                return

            user = await hass.auth.async_get_user(call.context.user_id)
            if user is None:
                raise UnknownUser(
                    context=call.context,
                    permission=POLICY_CONTROL
                )

            # If the user passes one or more entity IDs, check permissions
            # there; otherwise, check permissions against entities registered
            # to the domain:
            if call.data.get('entity_id'):
                if isinstance(call.data['entity'], str):
                    entities = [call.data['entity_id']]
                else:
                    entities = call.data['entity_id']
            else:
                reg = await hass.helpers.entity_registry.async_get_registry()
                entities = [
                    entity.entity_id for entity in reg.entities.values()
                    if entity.platform == domain
                ]

            for entity_id in entities:
                if user.permissions.check_entity(entity_id, POLICY_CONTROL):
                    return await service(call)

            raise Unauthorized(
                context=call.context,
                permission=POLICY_CONTROL,
            )
        return check_permissions
    return decorator


def lookup_all(perm_lookup: PermissionLookup, lookup_dict: SubCategoryDict,
               object_id: str) -> ValueType:
    """Look up permission for all."""
    # In case of ALL category, lookup_dict IS the schema.
    return cast(ValueType, lookup_dict)


def compile_policy(
        policy: CategoryType, subcategories: SubCatLookupType,
        perm_lookup: PermissionLookup
    ) -> Callable[[str, str], bool]:  # noqa
    """Compile policy into a function that tests policy.
    Subcategories are mapping key -> lookup function, ordered by highest
    priority first.
    """
    # None, False, empty dict
    if not policy:
        def apply_policy_deny_all(entity_id: str, key: str) -> bool:
            """Decline all."""
            return False

        return apply_policy_deny_all

    if policy is True:
        def apply_policy_allow_all(entity_id: str, key: str) -> bool:
            """Approve all."""
            return True

        return apply_policy_allow_all

    assert isinstance(policy, dict)

    funcs = []  # type: List[Callable[[str, str], Union[None, bool]]]

    for key, lookup_func in subcategories.items():
        lookup_value = policy.get(key)

        # If any lookup value is `True`, it will always be positive
        if isinstance(lookup_value, bool):
            return lambda object_id, key: True

        if lookup_value is not None:
            funcs.append(_gen_dict_test_func(
                perm_lookup, lookup_func, lookup_value))

    if len(funcs) == 1:
        func = funcs[0]

        @wraps(func)
        def apply_policy_func(object_id: str, key: str) -> bool:
            """Apply a single policy function."""
            return func(object_id, key) is True

        return apply_policy_func

    def apply_policy_funcs(object_id: str, key: str) -> bool:
        """Apply several policy functions."""
        for func in funcs:
            result = func(object_id, key)
            if result is not None:
                return result
        return False

    return apply_policy_funcs


def _gen_dict_test_func(
        perm_lookup: PermissionLookup,
        lookup_func: LookupFunc,
        lookup_dict: SubCategoryDict
    ) -> Callable[[str, str], Optional[bool]]:  # noqa
    """Generate a lookup function."""
    def test_value(object_id: str, key: str) -> Optional[bool]:
        """Test if permission is allowed based on the keys."""
        schema = lookup_func(
            perm_lookup, lookup_dict, object_id)  # type: ValueType

        if schema is None or isinstance(schema, bool):
            return schema

        assert isinstance(schema, dict)

        return schema.get(key)

    return test_value
