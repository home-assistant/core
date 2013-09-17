from datetime import datetime, timedelta

from app.observer.Timer import track_time_change

STATE_NH = 'NH'
STATE_NH5 = 'NH5'
STATE_H = 'H'
STATE_H5 = 'H5'

STATE_DEFAULT = STATE_NH5

# After how much time will we switch form NH to NH5 and H to H5 ?
TIME_SPAN_FOR_EXTRA_STATE = timedelta(minutes=5)

# After how much time do we consider a device not home if
# it does not show up on scans
# 70 seconds is to ensure 2 scans
TIME_SPAN_FOR_ERROR_IN_SCANNING = timedelta(seconds=70)

STATE_CATEGORY_ALL_DEVICES = 'device.alldevices'
STATE_CATEGORY_DEVICE_FORMAT = 'device.{}'



class DeviceTracker:

	def __init__(self, eventbus, statemachine, device_scanner):
		self.statemachine = statemachine
		self.eventbus = eventbus
		self.device_scanner = device_scanner

		default_last_seen = datetime(1990, 1, 1)
		now = datetime.now()

		temp_devices_to_track = device_scanner.get_devices_to_track()

		self.devices_to_track = { device: { 'name': temp_devices_to_track[device],
											'state': STATE_DEFAULT, 
											'last_seen': default_last_seen,
											'state_changed': now }
								  for device in temp_devices_to_track }

		self.all_devices_state = STATE_DEFAULT
		self.all_devices_state_changed = datetime.now()

		# Add categories to state machine
		statemachine.add_category(STATE_CATEGORY_ALL_DEVICES, STATE_DEFAULT)

		for device in self.devices_to_track:
			self.statemachine.add_category(STATE_CATEGORY_DEVICE_FORMAT.format(self.devices_to_track[device]['name']), STATE_DEFAULT)



		track_time_change(eventbus, lambda time: self.update_devices(device_scanner.scan_devices(time)))



	def device_state_categories(self):
		for device in self.devices_to_track:
			yield STATE_CATEGORY_DEVICE_FORMAT.format(self.devices_to_track[device]['name'])


	def set_state(self, device, state):
		if self.devices_to_track[device]['state'] != state:
			self.devices_to_track[device]['state'] = state
			self.devices_to_track[device]['state_changed'] = datetime.now()

			if state in [STATE_H]:
				self.devices_to_track[device]['last_seen'] = self.devices_to_track[device]['state_changed']

			self.statemachine.set_state(STATE_CATEGORY_DEVICE_FORMAT.format(self.devices_to_track[device]['name']), state)


	def update_devices(self, found_devices):
		temp_tracking_devices = self.devices_to_track.keys()

		for device in found_devices:
			# Are we tracking this device?
			if device in temp_tracking_devices:
				temp_tracking_devices.remove(device)

				# If home, check if for 5+ minutes, then change state to H5
				if self.devices_to_track[device]['state'] == STATE_H and \
					datetime.now() - self.devices_to_track[device]['state_changed'] > TIME_SPAN_FOR_EXTRA_STATE:
					
					self.set_state(device, STATE_H5)

				elif not self.devices_to_track[device]['state'] in [STATE_H, STATE_H5]:
					self.set_state(device, STATE_H)

		# For all devices we did not find, set state to NH
		# But only if they have been gone for longer then the error time span
		# Because we do not want to have stuff happening when the device does
		# not show up for 1 scan beacuse of reboot etc
		for device in temp_tracking_devices:
			if self.devices_to_track[device]['state'] in [STATE_H, STATE_H5] and \
				datetime.now() - self.devices_to_track[device]['last_seen'] > TIME_SPAN_FOR_ERROR_IN_SCANNING:

				self.set_state(device, STATE_NH)

			elif self.devices_to_track[device]['state'] == STATE_NH and \
				datetime.now() - self.devices_to_track[device]['last_seen'] > TIME_SPAN_FOR_EXTRA_STATE:

				self.set_state(device, STATE_NH5)


		# Get the set of currently used statuses
		states_of_devices = set( [self.devices_to_track[device]['state'] for device in self.devices_to_track] )

		# If there is only one status in use, that is the status of all devices
		if len(states_of_devices) == 1:
			self.all_devices_state = states_of_devices.pop()

		# Else if there is atleast 1 device home, the status is HOME
		elif STATE_H in states_of_devices or STATE_H5 in states_of_devices:
			self.all_devices_state = STATE_H

		# Else status is not home 
		else:
			self.all_devices_state = STATE_NH

		self.statemachine.set_state(STATE_CATEGORY_ALL_DEVICES, self.all_devices_state)
