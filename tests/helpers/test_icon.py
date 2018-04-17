"""Test Home Assistant icon util methods."""
import unittest


class TestIconUtil(unittest.TestCase):
    """Test icon util methods."""

    def test_battery_icon(self):
        """Test icon generator for battery sensor."""
        from homeassistant.helpers.icon import icon_for_battery_level

        self.assertEqual('mdi:battery-unknown',
                         icon_for_battery_level(None, True))
        self.assertEqual('mdi:battery-unknown',
                         icon_for_battery_level(None, False))

        self.assertEqual('mdi:battery-outline',
                         icon_for_battery_level(5, True))
        self.assertEqual('mdi:battery-alert',
                         icon_for_battery_level(5, False))

        self.assertEqual('mdi:battery-charging-100',
                         icon_for_battery_level(100, True))
        self.assertEqual('mdi:battery',
                         icon_for_battery_level(100, False))

        iconbase = 'mdi:battery'
        for level in range(0, 100, 5):
            print('Level: %d. icon: %s, charging: %s'
                  % (level, icon_for_battery_level(level, False),
                     icon_for_battery_level(level, True)))
            if level <= 10:
                postfix_charging = '-outline'
            elif level <= 30:
                postfix_charging = '-charging-20'
            elif level <= 50:
                postfix_charging = '-charging-40'
            elif level <= 70:
                postfix_charging = '-charging-60'
            elif level <= 90:
                postfix_charging = '-charging-80'
            else:
                postfix_charging = '-charging-100'
            if 5 < level < 95:
                postfix = '-{}'.format(int(round(level / 10 - .01)) * 10)
            elif level <= 5:
                postfix = '-alert'
            else:
                postfix = ''
            self.assertEqual(iconbase + postfix,
                             icon_for_battery_level(level, False))
            self.assertEqual(iconbase + postfix_charging,
                             icon_for_battery_level(level, True))
