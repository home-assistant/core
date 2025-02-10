"""Tests for the schema validators of the KNX integration."""

import gc
from typing import Any

import pytest
import voluptuous as vol
from voluptuous_serialize import UNSUPPORTED
from xknx.dpt import (
    DPT2ByteFloat,
    DPTBase,
    DPTDecimalFactor,
    DPTPercentU8,
    DPTSceneNumber,
    DPTSwitch,
    DPTTariff,
    DPTValue1ByteUnsigned,
    DPTValue1Ucount,
    DPTVoltage,
)

from homeassistant.components.knx.schema_ui import (
    ConfigGroupSchema,
    DptUtils,
    EntityConfigGroupSchema,
    GroupAddressConfigSchema,
    GroupAddressListSchema,
    GroupAddressSchema,
    PlatformConfigSchema,
    SchemaSerializer,
    SerializableSchema,
    SyncStateSchema,
)
from homeassistant.components.knx.storage.const import (
    CONF_DEVICE_INFO,
    CONF_DPT,
    CONF_GA_PASSIVE,
    CONF_GA_STATE,
    CONF_GA_WRITE,
)
from homeassistant.const import CONF_ENTITY_CATEGORY, CONF_NAME, EntityCategory


class TestDptUtils:
    """Test class for DptUtils utility methods using real DPT classes from the xknx library."""

    # Test data for the format_dpt method:
    # (1) test_name: descriptive name for the test
    # (2) dpt_class: the DPT class to format
    # (3) expected: the expected formatted string, or ValueError if an error is expected
    FORMAT_DPT_CASES: tuple[tuple[str, type, Any], ...] = (
        ("valid_dpt_binary", DPTSwitch, "1.001"),
        ("valid_dpt_temperature", DPT2ByteFloat, "9"),
        ("invalid_non_dpt", int, ValueError),
    )

    # Test data for the derive_subtypes method:
    # (1) test_name: descriptive name for the test
    # (2) input_types: a tuple of DPT classes to process
    # (3) expected: the expected tuple of derived DPT types
    DERIVE_SUBTYPES_CASES: tuple[
        tuple[str, tuple[type, ...], tuple[type, ...]], ...
    ] = (
        ("derive_leaf", (DPTSwitch,), (DPTSwitch,)),
        (
            "derive_base_class",
            (DPTValue1ByteUnsigned,),
            (
                DPTValue1ByteUnsigned,
                DPTPercentU8,
                DPTDecimalFactor,
                DPTTariff,
                DPTValue1Ucount,
                DPTSceneNumber,
            ),
        ),
        (
            "derive_multiple",
            (DPTValue1ByteUnsigned, DPTSwitch),
            (
                DPTValue1ByteUnsigned,
                DPTPercentU8,
                DPTDecimalFactor,
                DPTTariff,
                DPTValue1Ucount,
                DPTSceneNumber,
                DPTSwitch,
            ),
        ),
    )

    @pytest.mark.parametrize(
        ("test_name", "dpt_class", "expected"),
        FORMAT_DPT_CASES,
        ids=[case[0] for case in FORMAT_DPT_CASES],
    )
    def test_format_dpt(
        self,
        test_name: str,
        dpt_class: type[DPTBase],
        expected: Any,
    ) -> None:
        """Test the format_dpt static method of DptUtils.

        - If 'expected' is ValueError, a ValueError should be raised.
        - Otherwise, the returned string should match 'expected'.
        """
        if expected is ValueError:
            with pytest.raises(ValueError):
                DptUtils.format_dpt(dpt_class)
        else:
            result = DptUtils.format_dpt(dpt_class)
            assert result == expected, (
                f"Test case '{test_name}' failed: Expected '{expected}', got '{result}'."
            )

    @pytest.mark.parametrize(
        ("test_name", "input_types", "expected"),
        DERIVE_SUBTYPES_CASES,
        ids=[case[0] for case in DERIVE_SUBTYPES_CASES],
    )
    def test_derive_subtypes(
        self,
        test_name: str,
        input_types: tuple[type, ...],
        expected: tuple[type, ...],
    ) -> None:
        """Test the derive_subtypes static method of DptUtils.

        It should return a tuple of DPT classes from the provided input types
        that have distinct DPT numbers.
        """
        result = DptUtils.derive_subtypes(*input_types)
        assert result == expected, (
            f"Test case '{test_name}' failed: Expected {expected}, got {result}."
        )


class TestGroupAddressSchema:
    """Test class for GroupAddressSchema validation and serialization."""

    # Test cases for the __call__ method.
    # (1) test_name: descriptive name for the test
    # (2) input_value: the value to validate
    # (3) allow_internal_address: whether internal addresses are allowed
    # (4) expected: the expected result (either valid value or vol.Invalid)
    GROUP_ADDRESS_SCHEMA_CALL_CASES: tuple[tuple[str, Any, bool, Any], ...] = (
        ("valid_string_address", "1/2/3", False, "1/2/3"),
        ("valid_int_address", 123, False, 123),
        ("invalid_none", None, False, vol.Invalid),
        ("invalid_list_type", [1, 2], False, vol.Invalid),
        ("valid_internal_address", "i1/2/3", True, "i1/2/3"),
        ("invalid_internal_not_allowed", "i1/2/3", False, vol.Invalid),
        ("invalid_random_string", "abc", True, vol.Invalid),
    )

    # Test cases for the serialize method.
    # (1) test_name: descriptive name for the test
    # (2) init_options: constructor kwargs for GroupAddressSchema
    # (3) expected_allow_internal: expected boolean in the serialized dict
    GROUP_ADDRESS_SCHEMA_SERIALIZE_CASES: tuple[
        tuple[str, dict[str, bool], bool], ...
    ] = (
        ("defaults", {}, True),
        ("disallow_internal_address", {"allow_internal_address": False}, False),
        ("allow_internal_address_true", {"allow_internal_address": True}, True),
    )

    @pytest.mark.parametrize(
        ("test_name", "input_value", "allow_internal", "expected"),
        GROUP_ADDRESS_SCHEMA_CALL_CASES,
        ids=[case[0] for case in GROUP_ADDRESS_SCHEMA_CALL_CASES],
    )
    def test_group_address_schema_call(
        self,
        test_name: str,
        input_value: Any,
        allow_internal: bool,
        expected: Any,
    ) -> None:
        """Test the __call__ method of GroupAddressSchema.

        - If 'expected' is vol.Invalid, we expect a vol.Invalid exception.
        - Otherwise, we verify that the returned value matches 'expected'.
        """
        validator = GroupAddressSchema(allow_internal_address=allow_internal)

        if expected == vol.Invalid:
            with pytest.raises(vol.Invalid):
                validator(input_value)
        else:
            result = validator(input_value)
            assert result == expected, (
                f"Test case '{test_name}' failed: Expected '{expected}', got '{result}'."
            )

    @pytest.mark.parametrize(
        ("test_name", "init_options", "expected_allow_internal"),
        GROUP_ADDRESS_SCHEMA_SERIALIZE_CASES,
        ids=[case[0] for case in GROUP_ADDRESS_SCHEMA_SERIALIZE_CASES],
    )
    def test_group_address_schema_serialize(
        self,
        test_name: str,
        init_options: dict[str, bool],
        expected_allow_internal: bool,
    ) -> None:
        """Test the serialization method of GroupAddressSchema.

        Ensures that the returned dictionary has the correct 'type' value and
        includes 'allow_internal_address' from the instance options.
        """

        def mock_convert(schema: Any) -> Any:
            return "converted_schema"

        instance = GroupAddressSchema(**init_options)
        result = GroupAddressSchema.serialize(instance, mock_convert)

        assert isinstance(result, dict), "Serialization result must be a dictionary."
        assert result["type"] == "group_address", (
            f"Test case '{test_name}' failed: 'type' is not 'group_address'."
        )
        assert result["allow_internal_address"] == expected_allow_internal, (
            f"Test case '{test_name}' failed: 'allow_internal_address' mismatch."
        )

    def test_get_schema(self) -> None:
        """Test get_schema function."""

        instance = GroupAddressSchema()
        schema = instance.get_schema()
        assert isinstance(schema, vol.Schema | vol.All | vol.Any), (
            "get_schema should return a schema type."
        )


class TestGroupAddressListSchema:
    """Test class for GroupAddressListSchema validation and serialization."""

    # Test data for the __call__ method:
    # (1) test_name: descriptive name for the test
    # (2) input_value: the data to validate
    # (3) allow_internal_addresses: whether internal addresses are allowed
    # (4) expected: the expected result – either a list, an empty list, or vol.Invalid
    GROUP_ADDRESS_LIST_CALL_CASES: tuple[tuple[str, Any, bool, Any], ...] = (
        # A list of standard group addresses (strings) without internal addresses
        (
            "valid_list_string_ga_no_internal",
            ["1/2/3", "2/3/4"],
            False,
            ["1/2/3", "2/3/4"],
        ),
        # A list of int addresses without internal addresses
        ("valid_list_int_ga_no_internal", [123, 456], False, [123, 456]),
        # An empty list is valid
        ("valid_empty_list_no_internal", [], False, []),
        # None -> coerce to empty list
        ("valid_none_coerced_to_empty_list_no_internal", None, False, []),
        # False -> coerce to empty list
        ("valid_boolean_false_coerced_to_empty_list_no_internal", False, False, []),
        # True -> invalid
        ("invalid_boolean_true_no_internal", True, False, vol.Invalid),
        # Invalid single string instead of a list
        ("invalid_single_string_no_internal", "1/2/3", False, vol.Invalid),
        # Mixed list with a None value
        ("invalid_mixed_list_no_internal", [123, None], False, vol.Invalid),
        # Cases specifically for allow_internal_addresses=True
        (
            "valid_list_of_internal_addresses",
            ["i1/2/3", "i2/3/4"],
            True,
            ["i1/2/3", "i2/3/4"],
        ),
        # Mixed with an internal address not allowed
        (
            "invalid_internal_not_allowed_in_list",
            ["1/2/3", "i3/4/5"],
            False,
            vol.Invalid,
        ),
        # Invalid single internal address when a list is not given
        ("invalid_single_internal_as_non_list", "i1/2/3", True, vol.Invalid),
    )

    # Test data for the serialize method:
    # (1) test_name: descriptive name
    # (2) init_options: dict to pass to the constructor
    # (3) expected_allow_internal: the expected boolean in the underlying schema
    GROUP_ADDRESS_LIST_SERIALIZE_CASES: tuple[
        tuple[str, dict[str, bool], bool], ...
    ] = (
        # Default is allow_internal_addresses=True
        ("defaults", {}, True),
        ("disallow_internal", {"allow_internal_addresses": False}, False),
        ("allow_internal_true", {"allow_internal_addresses": True}, True),
    )

    @pytest.mark.parametrize(
        ("test_name", "input_value", "allow_internal", "expected"),
        GROUP_ADDRESS_LIST_CALL_CASES,
        ids=[case[0] for case in GROUP_ADDRESS_LIST_CALL_CASES],
    )
    def test_group_address_list_call(
        self,
        test_name: str,
        input_value: Any,
        allow_internal: bool,
        expected: Any,
    ) -> None:
        """Test the __call__ method of GroupAddressListSchema.

        - If 'expected' is vol.Invalid, we expect a vol.Invalid exception.
        - Otherwise, we verify that the returned list matches 'expected'.
        """
        validator = GroupAddressListSchema(allow_internal_addresses=allow_internal)

        if expected == vol.Invalid:
            with pytest.raises(vol.Invalid):
                validator(input_value)
        else:
            result = validator(input_value)
            assert result == expected, (
                f"Test case '{test_name}' failed: Expected {expected}, got {result}."
            )

    @pytest.mark.parametrize(
        ("test_name", "init_options", "expected_allow_internal"),
        GROUP_ADDRESS_LIST_SERIALIZE_CASES,
        ids=[case[0] for case in GROUP_ADDRESS_LIST_SERIALIZE_CASES],
    )
    def test_group_address_list_serialize(
        self,
        test_name: str,
        init_options: dict[str, bool],
        expected_allow_internal: bool,
    ) -> None:
        """Test the serialize method of GroupAddressListSchema.

        Ensures that the returned dictionary has the correct structure.
        'items' is the serialization of a GroupAddressSchema with the same allow_internal_addresses
        flag. We only see 'converted_schema' from the mock here, but we confirm it was used.
        """

        def mock_convert(_: Any) -> Any:
            return "converted_schema"

        instance = GroupAddressListSchema(**init_options)
        result = GroupAddressListSchema.serialize(instance, mock_convert)

        assert isinstance(result, dict), "Serialization result must be a dictionary."
        assert result["type"] == "group_address_list", (
            f"Test case '{test_name}' failed: 'type' is not 'group_address_list'."
        )
        assert result["items"] == "converted_schema", (
            f"Test case '{test_name}' failed: 'items' was not 'converted_schema'."
        )

        # Optionally, verify that the instance has the correct allow_internal_addresses
        assert instance.allow_internal_addresses == expected_allow_internal, (
            f"Test case '{test_name}' failed: allow_internal_addresses mismatch."
        )

    def test_get_schema(self) -> None:
        """Test get_schema function."""

        instance = GroupAddressListSchema()
        schema = instance.get_schema()
        assert isinstance(schema, vol.Schema | vol.All | vol.Any), (
            "get_schema should return a schema type."
        )


class TestSyncStateSchema:
    """Test class for SyncStateSchema validation and serialization."""

    # Test data for the __call__ method:
    # (1) test_name: descriptive name for the test
    # (2) input_value: the value to validate
    # (3) expected: either a valid output (if valid) or vol.Invalid (if invalid)
    SYNC_STATE_SCHEMA_CALL_CASES: tuple[tuple[str, Any, Any], ...] = (
        # Valid integers in range
        ("valid_int_min", 2, 2),
        ("valid_int_max", 1440, 1440),
        # Invalid integers
        ("invalid_int_below_min", 1, vol.Invalid),
        ("invalid_int_above_max", 1441, vol.Invalid),
        # Valid booleans
        ("valid_bool_true", True, True),
        ("valid_bool_false", False, False),
        # Valid strings matching the pattern
        ("valid_string_init", "init", "init"),
        ("valid_string_expire", "expire", "expire"),
        ("valid_string_every", "every", "every"),
        ("valid_string_every_number", "every 42", "every 42"),
        # Invalid strings (typo or extra non-digit info)
        ("invalid_string_typo", "expyre", vol.Invalid),
        ("invalid_string_pattern", "init abc", vol.Invalid),
    )

    # Test data for the serialize method:
    # (1) test_name: descriptive name for the test
    SYNC_STATE_SCHEMA_SERIALIZE_CASES: tuple[tuple[str], ...] = (
        ("serialize_default",),
    )

    @pytest.mark.parametrize(
        ("test_name", "input_value", "expected"),
        SYNC_STATE_SCHEMA_CALL_CASES,
        ids=[case[0] for case in SYNC_STATE_SCHEMA_CALL_CASES],
    )
    def test_sync_state_schema_call(
        self,
        test_name: str,
        input_value: Any,
        expected: Any,
    ) -> None:
        """Test the __call__ method of SyncStateSchema.

        - If 'expected' is vol.Invalid, we expect a vol.Invalid exception.
        - Otherwise, we check that the return value matches 'expected'.
        """
        validator = SyncStateSchema()

        if expected == vol.Invalid:
            with pytest.raises(vol.Invalid):
                validator(input_value)
        else:
            result = validator(input_value)
            assert result == expected, (
                f"Test case '{test_name}' failed: "
                f"Expected '{expected}', got '{result}'."
            )

    @pytest.mark.parametrize(
        "test_name",
        SYNC_STATE_SCHEMA_SERIALIZE_CASES,
        ids=[case[0] for case in SYNC_STATE_SCHEMA_SERIALIZE_CASES],
    )
    def test_sync_state_schema_serialize(self, test_name: str) -> None:
        """Test the serialization method of SyncStateSchema.

        Ensures that the returned dictionary has the correct 'type' value.
        """

        def mock_convert(schema: Any) -> Any:
            return "converted_schema"

        instance = SyncStateSchema()
        result = SyncStateSchema.serialize(instance, mock_convert)

        assert isinstance(result, dict), "Serialization result must be a dictionary."
        assert result["type"] == "sync_state", (
            f"Test case '{test_name}' failed: 'type' is not 'sync_state'."
        )

    def test_get_schema(self) -> None:
        """Test get_schema function."""

        instance = SyncStateSchema()
        schema = instance.get_schema()
        assert isinstance(schema, vol.Schema | vol.All | vol.Any), (
            "get_schema should return a schema type."
        )


class TestGroupAddressConfigSchema:
    """Test class for GroupAddressConfigSchema."""

    # Test cases for constructor validation (the __post_init__ checks).
    # (1) test_name: descriptive name
    # (2) constructor_kwargs: dictionary of arguments to pass into GroupAddressConfigSchema
    # (3) expect_error: True if we expect a ValueError, otherwise False
    CONFIG_CONSTRUCTOR_CASES: tuple[tuple[str, dict[str, Any], bool], ...] = (
        (
            "valid_minimal",
            {"allowed_dpts": (DPTVoltage,)},
            False,
        ),
        (
            "no_dpts_provided",
            {"allowed_dpts": ()},
            True,
        ),
        (
            "both_write_and_state_disabled",
            {"allowed_dpts": (DPTVoltage,), "write": False, "state": False},
            True,
        ),
        (
            "write_disabled_but_required",
            {"allowed_dpts": (DPTVoltage,), "write": False, "write_required": True},
            True,
        ),
        (
            "state_disabled_but_required",
            {"allowed_dpts": (DPTVoltage,), "state": False, "state_required": True},
            True,
        ),
        (
            "state_disabled_but_passive",
            {"allowed_dpts": (DPTVoltage,), "state": False, "passive": True},
            True,
        ),
    )

    # Test data for calling the schema with different data sets.
    # (1) test_name: descriptive name
    # (2) constructor_kwargs: arguments for GroupAddressConfigSchema
    # (3) input_data: the data dict to validate
    # (4) expected: the expected result – if vol.Invalid, we expect an exception,
    #               otherwise the validated dict
    CONFIG_CALL_CASES: tuple[tuple[str, dict[str, Any], dict[str, Any], Any], ...] = (
        (
            "dpt_provided_but_no_group_address",
            {"allowed_dpts": (DPTVoltage,)},
            {CONF_DPT: "9.020"},
            vol.Invalid,
        ),
        (
            "write_required_ok",
            {"allowed_dpts": (DPTVoltage,), "write_required": True},
            {CONF_GA_WRITE: "1/2/3", CONF_DPT: "9.020"},
            {
                CONF_GA_WRITE: "1/2/3",
                CONF_DPT: "9.020",
                CONF_GA_STATE: None,
                CONF_GA_PASSIVE: [],
            },
        ),
        (
            "write_required_missing",
            {"allowed_dpts": (DPTVoltage,), "write_required": True},
            {CONF_DPT: "9.020"},  # missing ga_write
            vol.Invalid,
        ),
        (
            "passive_ok",
            {"allowed_dpts": (DPTVoltage,), "passive": True},
            {
                CONF_DPT: "9.020",
                CONF_GA_PASSIVE: ["1/2/3"],
            },
            {
                CONF_DPT: "9.020",
                CONF_GA_PASSIVE: ["1/2/3"],
                CONF_GA_WRITE: None,
                CONF_GA_STATE: None,
            },
        ),
        (
            "dpt_not_allowed",
            {"allowed_dpts": (DPTVoltage,)},
            {CONF_GA_WRITE: "1/2/3", CONF_DPT: "9.001"},
            vol.Invalid,
        ),
    )

    # Test data for serialize method.
    # (1) test_name: descriptive name
    # (2) constructor_kwargs: arguments for GroupAddressConfigSchema
    CONFIG_SERIALIZE_CASES: tuple[tuple[str, dict[str, Any]], ...] = (
        ("default_serialize", {"allowed_dpts": (DPTVoltage,)}),
        (
            "serialize_all_options",
            {
                "allowed_dpts": (DPTVoltage,),
                "write": False,
                "state": True,
                "passive": False,
                "write_required": False,
                "state_required": False,
            },
        ),
    )

    @pytest.mark.parametrize(
        ("test_name", "constructor_kwargs", "expect_error"),
        CONFIG_CONSTRUCTOR_CASES,
        ids=[case[0] for case in CONFIG_CONSTRUCTOR_CASES],
    )
    def test_constructor_validation(
        self,
        test_name: str,
        constructor_kwargs: dict[str, Any],
        expect_error: bool,
    ) -> None:
        """Test the validation in __post_init__, ensuring that invalid configurations."""
        if expect_error:
            with pytest.raises(ValueError):
                GroupAddressConfigSchema(**constructor_kwargs)
        else:
            obj = GroupAddressConfigSchema(**constructor_kwargs)
            assert isinstance(obj.schema, vol.Schema), (
                f"Test case '{test_name}' failed: The 'schema' wasn't "
                f"initialized properly."
            )

    @pytest.mark.parametrize(
        ("test_name", "constructor_kwargs", "input_data", "expected"),
        CONFIG_CALL_CASES,
        ids=[case[0] for case in CONFIG_CALL_CASES],
    )
    def test_call_schema(
        self,
        test_name: str,
        constructor_kwargs: dict[str, Any],
        input_data: dict[str, Any],
        expected: Any,
    ) -> None:
        """Test the __call__ method of GroupAddressConfigSchema with various inputs.

        - If 'expected' is vol.Invalid, we expect a vol.Invalid exception.
        - Otherwise, we verify the validated dict matches 'expected'.
        """
        # Ensure constructor validation doesn't fail
        instance = GroupAddressConfigSchema(**constructor_kwargs)

        if expected == vol.Invalid:
            with pytest.raises(vol.Invalid):
                instance(input_data)
        else:
            result = instance(input_data)
            assert result == expected, (
                f"Test case '{test_name}' failed: Expected {expected}, got {result}."
            )

    @pytest.mark.parametrize(
        ("test_name", "constructor_kwargs"),
        CONFIG_SERIALIZE_CASES,
        ids=[case[0] for case in CONFIG_SERIALIZE_CASES],
    )
    def test_serialize(
        self,
        test_name: str,
        constructor_kwargs: dict[str, Any],
    ) -> None:
        """Test the serialize method of GroupAddressConfigSchema.

        Ensures that the returned dictionary has 'type'='group_address_config'
        and 'properties' as the converted schema.
        """

        def mock_convert(schema: Any) -> Any:
            return "converted_schema"

        instance = GroupAddressConfigSchema(**constructor_kwargs)
        result = GroupAddressConfigSchema.serialize(instance, mock_convert)

        assert isinstance(result, dict), "Serialization result must be a dictionary."
        assert result["type"] == "group_address_config", (
            f"Test case '{test_name}' failed: 'type' is not 'group_address_config'."
        )
        assert result["properties"] == "converted_schema", (
            f"Test case '{test_name}' failed: 'properties' was not 'converted_schema'."
        )

    def test_get_schema(self) -> None:
        """Test get_schema function."""

        instance = GroupAddressConfigSchema(allowed_dpts=(DPTVoltage,))
        schema = instance.get_schema()
        assert isinstance(schema, vol.Schema | vol.All | vol.Any), (
            "get_schema should return a schema type."
        )


class TestConfigGroupSchema:
    """Test class for ConfigGroupSchema validation and serialization."""

    SAMPLE_SCHEMA = vol.Schema({"key": str})

    # Test data for the __call__ method:
    # (1) test_name: descriptive name for the test
    # (2) input_value: the data to validate (a dict to be validated by SAMPLE_SCHEMA)
    # (3) ui_options: the UI options to initialize the ConfigGroupSchema (as a dict) or None for defaults
    # (4) expected: the expected result – either the validated dict or vol.Invalid if validation should fail
    CONFIG_GROUP_SCHEMA_CALL_CASES: tuple[
        tuple[str, dict[str, Any], dict[str, bool] | None, Any], ...
    ] = (
        (
            "valid_default_ui_options",
            {"key": "hello"},
            None,  # Defaults to {"collapsible": False}
            {"key": "hello"},
        ),
        (
            "invalid_schema_input",
            {"key": 123},
            None,
            vol.Invalid,
        ),
        (
            "valid_custom_ui_options",
            {"key": "world"},
            {"collapsible": True},
            {"key": "world"},
        ),
    )

    # Test data for invalid UI options during initialization:
    # (1) test_name: descriptive name for the test
    # (2) ui_options: the UI options that are invalid
    CONFIG_GROUP_SCHEMA_INVALID_UI_OPTIONS: tuple[tuple[str, dict[str, Any]], ...] = (
        (
            "invalid_ui_options_non_bool",
            {"collapsible": "yes"},
        ),
    )

    # Test data for the serialize method:
    # (1) test_name: descriptive name for the test
    # (2) ui_options: the UI options to initialize the ConfigGroupSchema (as a dict) or None for defaults
    # (3) expected_ui_options: the expected UI options in the serialized output (a dict)
    CONFIG_GROUP_SCHEMA_SERIALIZE_CASES: tuple[
        tuple[str, dict[str, bool] | None, dict[str, Any]], ...
    ] = (
        (
            "serialize_default",
            None,  # Defaults to {"collapsible": False}
            {"collapsible": False},
        ),
        (
            "serialize_collapsible_true",
            {"collapsible": True},
            {"collapsible": True},
        ),
    )

    @pytest.mark.parametrize(
        ("test_name", "input_value", "ui_options", "expected"),
        CONFIG_GROUP_SCHEMA_CALL_CASES,
        ids=[case[0] for case in CONFIG_GROUP_SCHEMA_CALL_CASES],
    )
    def test_config_group_schema_call(
        self,
        test_name: str,
        input_value: dict[str, Any],
        ui_options: ConfigGroupSchema.UIOptions | None,
        expected: Any,
    ) -> None:
        """Test the __call__ method of ConfigGroupSchema.

        It validates input data against SAMPLE_SCHEMA using provided UI options.
        If 'expected' is vol.Invalid, a vol.Invalid exception should be raised.
        Otherwise, the output should match 'expected'.
        """
        instance = ConfigGroupSchema(self.SAMPLE_SCHEMA, ui_options)
        if expected == vol.Invalid:
            with pytest.raises(vol.Invalid):
                instance(input_value)
        else:
            result = instance(input_value)
            assert result == expected, (
                f"Test case '{test_name}' failed: Expected {expected}, got {result}."
            )

    @pytest.mark.parametrize(
        ("test_name", "ui_options"),
        CONFIG_GROUP_SCHEMA_INVALID_UI_OPTIONS,
        ids=[case[0] for case in CONFIG_GROUP_SCHEMA_INVALID_UI_OPTIONS],
    )
    def test_config_group_schema_invalid_ui_options(
        self,
        test_name: str,
        ui_options: ConfigGroupSchema.UIOptions,
    ) -> None:
        """Test that constructing ConfigGroupSchema with invalid UI options raises vol.Invalid.

        For example, if 'collapsible' is not a boolean, the UI_OPTIONS_SCHEMA should throw.
        """
        with pytest.raises(vol.Invalid):
            ConfigGroupSchema(self.SAMPLE_SCHEMA, ui_options)

    @pytest.mark.parametrize(
        ("test_name", "ui_options", "expected_ui_options"),
        CONFIG_GROUP_SCHEMA_SERIALIZE_CASES,
        ids=[case[0] for case in CONFIG_GROUP_SCHEMA_SERIALIZE_CASES],
    )
    def test_config_group_schema_serialize(
        self,
        test_name: str,
        ui_options: ConfigGroupSchema.UIOptions | None,
        expected_ui_options: dict[str, Any],
    ) -> None:
        """Test the serialize method of ConfigGroupSchema.

        The serialization should return a dictionary with:
          - "type": "config_group"
          - "ui_options": matching expected_ui_options
          - "properties": the converted schema from a mock converter.
        """

        def mock_convert(schema: Any) -> Any:
            return "converted_schema"

        instance = ConfigGroupSchema(self.SAMPLE_SCHEMA, ui_options)
        result = ConfigGroupSchema.serialize(instance, mock_convert)

        assert isinstance(result, dict), (
            f"Test case '{test_name}' failed: result is not a dict."
        )
        assert result.get("type") == "config_group", (
            f"Test case '{test_name}' failed: 'type' is not 'config_group'."
        )
        assert result.get("properties") == "converted_schema", (
            f"Test case '{test_name}' failed: 'properties' mismatch."
        )
        assert result.get("ui_options") == expected_ui_options, (
            f"Test case '{test_name}' failed: expected ui_options {expected_ui_options}, got {result.get('ui_options')}."
        )

    def test_get_schema(self) -> None:
        """Test the schema property of ConfigGroupSchema."""
        instance = ConfigGroupSchema(self.SAMPLE_SCHEMA)
        schema = instance.get_schema()
        assert isinstance(schema, vol.Schema | vol.All | vol.Any), (
            "get_schema should return a schema type."
        )
        assert schema == self.SAMPLE_SCHEMA, (
            "The 'schema' property should return the schema passed to the constructor."
        )


class TestEntityConfigGroupSchema:
    """Test class for EntityConfigGroupSchema validation and serialization."""

    # Test data for the __call__ method:
    # (1) test_name: descriptive name for the test
    # (2) input_value: the data to validate (a dict to be validated by the schema)
    # (3) expected: the expected result – either the validated dict or vol.Invalid if validation should fail
    ENTITY_CONFIG_CALL_CASES: tuple[tuple[str, dict[str, Any], Any], ...] = (
        (
            "valid_minimal",
            {CONF_NAME: "My Entity"},
            {
                CONF_NAME: "My Entity",
                CONF_ENTITY_CATEGORY: None,
                CONF_DEVICE_INFO: None,
            },
        ),
        (
            "valid_full",
            {
                CONF_NAME: "My Entity",
                CONF_ENTITY_CATEGORY: EntityCategory.CONFIG,
                CONF_DEVICE_INFO: "knx_vdev_01JK5K7GSS6R7S6Q7P5K7M7SMF",
            },
            {
                CONF_NAME: "My Entity",
                CONF_ENTITY_CATEGORY: EntityCategory.CONFIG,
                CONF_DEVICE_INFO: "knx_vdev_01JK5K7GSS6R7S6Q7P5K7M7SMF",
            },
        ),
        (
            "invalid_missing_name",
            {CONF_ENTITY_CATEGORY: EntityCategory.CONFIG},
            vol.Invalid,
        ),
        (
            "invalid_wrong_category",
            {
                CONF_NAME: "My Entity",
                CONF_ENTITY_CATEGORY: "invalid",  # not a valid EntityCategory
                CONF_DEVICE_INFO: "knx_vdev_01JK5K7GSS6R7S6Q7P5K7M7SMF",
            },
            vol.Invalid,
        ),
        (
            "invalid_device_info_type",
            {CONF_NAME: "My Entity", CONF_DEVICE_INFO: 123},
            vol.Invalid,
        ),
    )

    # Test data for the serialize method:
    # (1) test_name: descriptive name for the test
    # (2) allowed_categories: the allowed EntityCategory values to initialize the schema
    # (3) expected_ui_options: the expected ui_options in the serialized output (a dict)
    ENTITY_CONFIG_SERIALIZE_CASES: tuple[
        tuple[str, tuple[EntityCategory, ...], dict[str, Any]], ...
    ] = (
        (
            "serialize_default",
            (EntityCategory.CONFIG, EntityCategory.DIAGNOSTIC),
            {"collapsible": False},
        ),
    )

    @pytest.mark.parametrize(
        ("test_name", "input_value", "expected"),
        ENTITY_CONFIG_CALL_CASES,
        ids=[case[0] for case in ENTITY_CONFIG_CALL_CASES],
    )
    def test_entity_config_group_schema_call(
        self,
        test_name: str,
        input_value: dict[str, Any],
        expected: Any,
    ) -> None:
        """Test the __call__ method of EntityConfigGroupSchema.

        It validates input data against the constructed schema.
        If 'expected' is vol.Invalid, a vol.Invalid exception should be raised.
        Otherwise, the validated output should match 'expected'.
        """
        instance = EntityConfigGroupSchema(
            allowed_categories=(EntityCategory.CONFIG, EntityCategory.DIAGNOSTIC)
        )
        if expected == vol.Invalid:
            with pytest.raises(vol.Invalid):
                instance(input_value)
        else:
            result = instance(input_value)
            assert result == expected, (
                f"Test case '{test_name}' failed: Expected {expected}, got {result}."
            )

    @pytest.mark.parametrize(
        ("test_name", "allowed_categories", "expected_ui_options"),
        ENTITY_CONFIG_SERIALIZE_CASES,
        ids=[case[0] for case in ENTITY_CONFIG_SERIALIZE_CASES],
    )
    def test_entity_config_group_schema_serialize(
        self,
        test_name: str,
        allowed_categories: tuple[EntityCategory, ...],
        expected_ui_options: dict[str, Any],
    ) -> None:
        """Test the serialize method of EntityConfigGroupSchema.

        The serialization should return a dictionary with:
          - "type": "config_group"
          - "ui_options": containing "collapsible" from the UI options (defaulting to False)
          - "properties": the converted schema from a mock converter.
        """

        def mock_convert(schema: Any) -> Any:
            return "converted_schema"

        instance = EntityConfigGroupSchema(allowed_categories=allowed_categories)
        result = EntityConfigGroupSchema.serialize(instance, mock_convert)

        assert isinstance(result, dict), (
            f"Test case '{test_name}' failed: result is not a dict."
        )
        assert result.get("type") == "config_group", (
            f"Test case '{test_name}' failed: type is not 'config_group'."
        )
        assert result.get("ui_options") == expected_ui_options, (
            f"Test case '{test_name}' failed: expected ui_options {expected_ui_options}, got {result.get('ui_options')}."
        )
        assert result.get("properties") == "converted_schema", (
            f"Test case '{test_name}' failed: properties mismatch."
        )

    def test_get_schema(self) -> None:
        """Test get_schema function."""

        instance = EntityConfigGroupSchema(allowed_categories=(EntityCategory.CONFIG,))
        schema = instance.get_schema()
        assert isinstance(schema, vol.Schema | vol.All | vol.Any), (
            "get_schema should return a schema type."
        )


class TestPlatformConfigSchema:
    """Test class for PlatformConfigSchema validation and serialization."""

    # A sample configuration schema for testing.
    SAMPLE_CONFIG_SCHEMA = vol.Schema({"key": str})

    # Test data for the __call__ method:
    # (1) test_name: descriptive name for the test
    # (2) input_value: the data to validate (a dict with "platform" and "config" keys)
    # (3) expected: the expected result – either the validated dict or vol.Invalid if validation should fail.
    PLATFORM_CONFIG_CALL_CASES: tuple[tuple[str, dict[str, Any], Any], ...] = (
        (
            "valid_platform_config",
            {"platform": "test_platform", "config": {"key": "hello"}},
            {"platform": "test_platform", "config": {"key": "hello"}},
        ),
        (
            "invalid_platform",
            {"platform": "wrong_platform", "config": {"key": "hello"}},
            vol.Invalid,
        ),
        (
            "invalid_config",
            {"platform": "test_platform", "config": {"key": 123}},
            vol.Invalid,
        ),
        (
            "missing_config",
            {"platform": "test_platform"},
            vol.Invalid,
        ),
    )

    @pytest.mark.parametrize(
        ("test_name", "input_value", "expected"),
        PLATFORM_CONFIG_CALL_CASES,
        ids=[case[0] for case in PLATFORM_CONFIG_CALL_CASES],
    )
    def test_platform_config_schema_call(
        self,
        test_name: str,
        input_value: dict[str, Any],
        expected: Any,
    ) -> None:
        """Test the __call__ method of PlatformConfigSchema.

        It validates input data against a schema constructed with a fixed platform ("test_platform")
        and a configuration schema (SAMPLE_CONFIG_SCHEMA). If 'expected' is vol.Invalid,
        a vol.Invalid exception should be raised. Otherwise, the validated output should match 'expected'.
        """
        instance = PlatformConfigSchema("test_platform", self.SAMPLE_CONFIG_SCHEMA)
        if expected == vol.Invalid:
            with pytest.raises(vol.Invalid):
                instance(input_value)
        else:
            result = instance(input_value)
            assert result == expected, (
                f"Test case '{test_name}' failed: Expected {expected}, got {result}."
            )

    def test_platform_config_schema_serialize(
        self,
    ) -> None:
        """Test the serialize method of PlatformConfigSchema.

        The serialization should return a dictionary with:
          - "type": "platform_config"
          - "properties": the output from the provided converter.
        """

        def mock_convert(schema: Any) -> Any:
            return "converted_schema"

        instance = PlatformConfigSchema("test_platform", self.SAMPLE_CONFIG_SCHEMA)
        result = PlatformConfigSchema.serialize(instance, mock_convert)
        assert isinstance(result, dict), "Test case failed: result is not a dict."
        assert result.get("type") == "platform_config", (
            "Test case failed: 'type' is not 'platform_config'."
        )
        assert result.get("properties") == "converted_schema", (
            f"Test case failed: Expected properties 'converted_schema', got '{result.get('properties')}'."
        )

    def test_get_schema(self) -> None:
        """Test get_schema function."""

        instance = PlatformConfigSchema(
            platform="test_platform", config_schema=self.SAMPLE_CONFIG_SCHEMA
        )
        schema = instance.get_schema()
        assert isinstance(schema, vol.Schema | vol.All | vol.Any), (
            "get_schema should return a schema type."
        )


class TestSchemaSerializer:
    """Test class for SchemaSerializer conversion and serialization logic."""

    class UnsupportedClass:
        """Placeholder class for testing unsupported types."""

    # Test data for `_serializer`
    # (1) test_name: descriptive name
    # (2) input_value: an instance or value
    # (3) expected: dict if supported, else UNSUPPORTED
    SERIALIZER_CASES: tuple[tuple[str, Any, Any], ...] = (
        (
            "supported_fake_schema",
            ConfigGroupSchema(vol.Schema({"key": str})),
            {
                "type": "config_group",
                "properties": [{"name": "key", "type": "string"}],
                "ui_options": {"collapsible": False},
            },
        ),
        ("unsupported_int", 999, UNSUPPORTED),
        ("unsupported_string", "Not recognized", UNSUPPORTED),
        ("unsupported_class", UnsupportedClass(), UNSUPPORTED),
        (
            "simple_dict_keys",
            {"alpha": "test_value", "beta": 123},
            [
                {"name": "alpha", "type": "constant", "value": "test_value"},
                {"name": "beta", "type": "constant", "value": 123},
            ],
        ),
        (
            "required_and_optional",
            {
                vol.Required("req_key", default="default_req"): "REQ_VAL",
                vol.Optional("opt_key", default="default_opt"): "OPT_VAL",
            },
            [
                {
                    "default": "default_req",
                    "name": "req_key",
                    "required": True,
                    "type": "constant",
                    "value": "REQ_VAL",
                },
                {
                    "default": "default_opt",
                    "name": "opt_key",
                    "optional": True,
                    "type": "constant",
                    "value": "OPT_VAL",
                },
            ],
        ),
        (
            "remove_marker_key",
            {"keep_this": "keeping", vol.Remove("skip_this"): "skipped"},
            [{"name": "keep_this", "type": "constant", "value": "keeping"}],
        ),
        (
            "marker_with_description",
            {vol.Required("key", description="A key"): "value"},
            [
                {
                    "description": "A key",
                    "name": "key",
                    "required": True,
                    "type": "constant",
                    "value": "value",
                }
            ],
        ),
    )

    # Test data for the `convert` method:
    # (1) test_name
    # (2) input_value
    # (3) expected: dict/list if convertible, or an exception type if it fails
    CONVERT_CASES: tuple[tuple[str, Any, Any], ...] = (
        (
            "convert_supported_type",
            ConfigGroupSchema(vol.Schema({"key": str})),
            {
                "type": "config_group",
                "ui_options": {"collapsible": False},
                "properties": [{"name": "key", "type": "string"}],
            },
        ),
        (
            "convert_simple_dict",
            {"k": "v"},
            [{"name": "k", "type": "constant", "value": "v"}],
        ),
        (
            "convert_unsupported_class",
            UnsupportedClass,  # Unsupported type, can by anything
            # UnsupportedClass(), # Should replace upper line when home-assistant-libs/voluptuous-serialize#140 is merged
            ValueError,  # We'll assume a ValueError if it fails
        ),
    )

    @pytest.mark.parametrize(
        ("test_name", "input_value", "expected"),
        SERIALIZER_CASES,
        ids=[case[0] for case in SERIALIZER_CASES],
    )
    def test_serializer(
        self,
        test_name: str,
        input_value: Any,
        expected: Any,
    ) -> None:
        """Test _serializer with a single supported type or unsupported values.

        - If it's a recognized type, we expect a dict from serialize().
        - Otherwise, we get UNSUPPORTED.
        """
        result = SchemaSerializer._serializer(input_value)
        assert result == expected, (
            f"Test '{test_name}' failed: Expected {expected}, got {result}"
        )

    @pytest.mark.parametrize(
        ("test_name", "input_value", "expected"),
        CONVERT_CASES,
        ids=[case[0] for case in CONVERT_CASES],
    )
    def test_convert_method(
        self,
        test_name: str,
        input_value: Any,
        expected: Any,
    ) -> None:
        """Test the SchemaSerializer.convert method."""

        if isinstance(expected, type) and issubclass(expected, Exception):
            with pytest.raises(expected):
                SchemaSerializer.convert(input_value)
        else:
            result = SchemaSerializer.convert(input_value)
            assert result == expected, (
                f"Test '{test_name}' failed: Expected {expected}, got {result}"
            )

    def test_all_serializable_types_are_registered(self) -> None:
        """Ensure all discovered SerializableSchema classes are registered in SchemaSerializer."""
        discovered_classes = set()

        for obj in gc.get_objects():
            if isinstance(obj, type):
                try:
                    if (
                        issubclass(obj, SerializableSchema)
                        and obj is not SerializableSchema
                        and "serialize" in obj.__dict__
                    ):
                        discovered_classes.add(obj)
                except TypeError:
                    continue

        assert discovered_classes == set(SchemaSerializer._supported_types), (
            "Mismatch between discovered SerializableSchema classes and SchemaSerializer._supported_types."
        )
