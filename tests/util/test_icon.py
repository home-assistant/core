"""Test Home Assistant icon util methods."""
import unittest


class TestIconUtil(unittest.TestCase):
    """Test icon util methods."""

    def test_battery_icon(self):
        """Test icon generator for battery sensor."""
        from homeassistant.util.icon import icon_for_battery_level

        self.assertEqual('mdi:battery-unknown',
                         icon_for_battery_level(None, True))
        self.assertEqual('mdi:battery-unknown',
                         icon_for_battery_level(None, False))

        iconbase = 'mdi:battery'
        for level in range(0, 105, 5):
            print('Level: %d. icon: %s, charging: %s'
                  % (level, icon_for_battery_level(level, False),
                     icon_for_battery_level(level, True)))
            if level < 20:
                postfix = '-outline'
            elif level < 40:
                postfix = '-20'
            elif level < 60:
                postfix = '-40'
            elif level < 80:
                postfix = '-60'
            elif level < 100:
                postfix = '-80'
            else:
                postfix = ''
            self.assertEqual(iconbase + postfix,
                             icon_for_battery_level(level, False))
            self.assertEqual(iconbase + '-charging' + postfix,
                             icon_for_battery_level(level, True))
