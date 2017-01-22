"""Test the customize helper."""
import homeassistant.helpers.customize as customize


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
        customize.set_customize(self.hass, overrides)
        return customize.get_overrides(self.hass, self.entity_id)

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
        """Test we can overwrite hidden property to True."""
        result = self._get_overrides(
            [{'entity_id': [self.entity_id],
              'test': {'key1': 'value1', 'key2': 'value2'}},
             {'entity_id': [self.entity_id],
              'test': {'key3': 'value3', 'key2': 'value22'}}])
        assert result['test'] == {
            'key1': 'value1',
            'key2': 'value22',
            'key3': 'value3'}
