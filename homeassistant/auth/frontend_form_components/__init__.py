"""This module provides a schema serializer and base classes for Frontend components inside auth flow forms."""
import collections.abc
from typing import Any

import voluptuous
from voluptuous import Marker
import voluptuous_serialize


class FrontendFormComponent:
    """
    This class represents a Frontend field form.

    this is the name of the component to be shown in the form frontend-side.
    Any component may have an object containing instantiation options, this is defined by component_options_schema
    """

    def __init__(
        self, component_name: str, component_options_schema: voluptuous.Schema
    ) -> None:
        """Init method for frontend defined form component."""
        self.component_name = component_name
        self.component_options_schema = component_options_schema

    def to_dict(self, options: dict[str, Any]) -> dict:
        """Return the dict representation of the frontend form directive to be sent via ws."""
        return {
            "component_name": self.component_name,
            "options": self.component_options_schema(options),
        }


class FrontendFormField(Marker):  # type: ignore[misc]
    """
    Marker for voluptuous Schema to represent a Frontend component to be inserted in the form.

    simply use this marker as a wrapper on a schema key to represent a frontend field.

    usage: vol.Schema({FrontendFormField(voluptuous.Required("<return_field_name>"), componentInstance, ...): <type>}
    where componentInstance is an instance of FrontendFormComponent

    A frontend field porpoise is to make the frontend side capable of performing actions in order to generate a
    response to be sent to the backend.
    For example, a FrontendFormField can be used to perform some kind of frontend-bound action
    (like authentication in a 2factor environment like Webauthn, file upload or captcha) and successively return
    the result for the backend to validate.
    """

    def __init__(
        self,
        schema: Any,
        component: FrontendFormComponent,
        msg: Any = None,
        description: Any = None,
        **kwargs: Any,
    ) -> None:
        """Init method."""
        super().__init__(schema, msg=msg, description=description)
        self.component = component
        self.options = kwargs


def _frontend_field_serializer(
    schema: dict[voluptuous.Schema, Any]
) -> collections.abc.Generator:
    """
    Return a generator for Schema serialization including FrontendFormFields.

    Internal function to generate the serialized data from a schema.
    see voluptuous reference on custom_serializers
    """
    for key, value in schema.items():
        if isinstance(key, FrontendFormField):
            yield {
                **voluptuous_serialize.convert({key.schema: value})[0],
                **key.component.to_dict(key.options),
                "type": "frontend-component",
            }
        else:
            yield voluptuous_serialize.convert({key: value})[0]


def frontend_field_schema_serializer(schema: dict[voluptuous.Schema, Any]) -> list:
    """Voluptuous custom serializer to support FrontendFields."""
    return list(_frontend_field_serializer(schema))
