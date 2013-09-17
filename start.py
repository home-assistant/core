import time

from app.Dependencies import Dependencies

from app.observer.WeatherWatcher import WeatherWatcher
from app.observer.DeviceTracker import DeviceTracker
from app.observer.TomatoDeviceScanner import TomatoDeviceScanner
from app.observer.Timer import Timer

from app.actor.HueTrigger import HueTrigger

deps = Dependencies()

weather = WeatherWatcher(deps.get_config(), deps.get_event_bus(), deps.get_state_machine())

tomato = TomatoDeviceScanner(deps.get_config())

device_tracker = DeviceTracker(deps.get_event_bus(), deps.get_state_machine(), tomato)

HueTrigger(deps.get_config(), deps.get_event_bus(), deps.get_state_machine(), device_tracker)


timer = Timer(deps.get_event_bus())
timer.start()

while True:
	try:
		time.sleep(1)

	except:
		print ""
		print "Interrupt received. Wrapping up and quiting.."
		timer.stop()
		break