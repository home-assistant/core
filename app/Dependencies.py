from ConfigParser import SafeConfigParser

from app.StateMachine import StateMachine
from app.EventBus import EventBus
from app.Logging import EventLogger

class Dependencies:

	def __init__(self):
		self.config = None
		self.eventbus = None
		self.statemachine = None


	def get_config(self):
		if self.config is None:
			self.config = SafeConfigParser()
			self.config.read("home-assistant.conf")

		return self.config

	def get_event_bus(self):
		if self.eventbus is None:
			self.eventbus = EventBus()
			#EventLogger(self.eventbus)

		return self.eventbus

	def get_state_machine(self):
		if self.statemachine is None:
			self.statemachine = StateMachine(self.get_event_bus())

		return self.statemachine

