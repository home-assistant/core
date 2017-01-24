"""Test the customize helper."""
import homeassistant.helpers.customize as customize
from voluptuous import MultipleInvalid, ALLOW_EXTRA
import pytest


class MockHass(object):
    """Mock object for HassAssistant."""

    data = {}


class TestHelpersCustomize(object):
    """Test homeassistant.helpers.customize module."""

    def setup_method(self, method):
        """Setup things to be run when tests are started."""
        self.entity_id = 'test.test'
        self.hass = MockHass()

    def _get_overrides(self, overrides):
        test_domain = 'test.domain'
        customize.set_customize(self.hass, test_domain, overrides)
        return customize.get_overrides(self.hass, test_domain, self.entity_id)

    def test_override_single_value(self):
        """Test entity customization through configuration."""
        result = self._get_overrides([
            {'entity_id': [self.entity_id], 'key': 'value'}])

        assert result == {'key': 'value'}

    def test_override_multiple_values(self):
        """Test entity customization through configuration."""
        result = self._get_overrides([
            {'entity_id': [self.entity_id], 'key1': 'value1'},
            {'entity_id': [self.entity_id], 'key2': 'value2'}])

        assert result == {'key1': 'value1', 'key2': 'value2'}

    def test_override_same_value(self):
        """Test entity customization through configuration."""
        result = self._get_overrides([
            {'entity_id': [self.entity_id], 'key': 'value1'},
            {'entity_id': [self.entity_id], 'key': 'value2'}])

        assert result == {'key': 'value2'}

    def test_override_by_domain(self):
        """Test entity customization through configuration."""
        result = self._get_overrides([
            {'entity_id': ['test'], 'key': 'value'}])

        assert result == {'key': 'value'}

    def test_override_by_glob(self):
        """Test entity customization through configuration."""
        result = self._get_overrides([
            {'entity_id': ['test.?e*'], 'key': 'value'}])

        assert result == {'key': 'value'}

    def test_override_exact_over_glob_over_domain(self):
        """Test entity customization through configuration."""
        result = self._get_overrides([
            {'entity_id': ['test.test'], 'key1': 'valueExact'},
            {'entity_id': ['test.tes?'],
             'key1': 'valueGlob',
             'key2': 'valueGlob'},
            {'entity_id': ['test'],
             'key1': 'valueDomain',
             'key2': 'valueDomain',
             'key3': 'valueDomain'}])

        assert result == {
            'key1': 'valueExact',
            'key2': 'valueGlob',
            'key3': 'valueDomain'}

    def test_override_deep_dict(self):
        """Test we can deep-overwrite a dict."""
        result = self._get_overrides(
            [{'entity_id': [self.entity_id],
              'test': {'key1': 'value1', 'key2': 'value2'}},
             {'entity_id': [self.entity_id],
              'test': {'key3': 'value3', 'key2': 'value22'}}])
        assert result['test'] == {
            'key1': 'value1',
            'key2': 'value22',
            'key3': 'value3'}

    def test_get_customize_schema_bad_schema(self):
        """Test bad customize schemas."""
        for value in (
                {'test.test': 10},
                {'test.test': ['hello']},
                {'test.test': {'hidden': True}},
                {'entity_id': {'a': 'b'}},
                {'entity_id': 10},
                [{'test.test': 'value'}],
                [{'entity_id': 'test', 'key': 'value'}],
        ):
            with pytest.raises(MultipleInvalid):
                customize.get_customize_schema()(value)

    def test_get_customize_schema_allow_extra(self):
        """Test schema with ALLOW_EXTRA."""
        schema = customize.get_customize_schema(extra=ALLOW_EXTRA)
        for value in (
                {'test.test': {'hidden': True}},
                {'test.test': {'key': ['value1', 'value2']}},
                [{'entity_id': 'id1', 'key': 'value'}],
        ):
            schema(value)

    def test_get_customize_schema_additional_key(self):
        """Test schema with extra keys."""
        schema = customize.get_customize_schema(schema={'key': 'value'})

        for value in (
                {'test.test': {'key': 'value1'}},
                {'test.test': {'key1': 'value'}},
                {'test.test': {'key': 'value', 'key1': 'value1'}},
        ):
            with pytest.raises(MultipleInvalid):
                schema(value)

        for value in (
                {'test.test': {'key': 'value'}},
                [{'entity_id': 'id1', 'key': 'value'}],
        ):
            schema(value)

    def test_get_customize_schema_csv(self):
        """Test schema with comma separated entity IDs."""
        schema = customize.get_customize_schema()

        assert [{'entity_id': ['id1', 'id2', 'id3']}] == schema(
            [{'entity_id': 'id1,ID2 , id3'}])
