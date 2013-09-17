import time
import logging

from app.EventBus import ALL_EVENTS


class EventLogger:

	def __init__(self, eventbus):
		eventbus.listen(ALL_EVENTS, self.log)
		self.logger = logging.getLogger("EventLogger")

	def log(self, event):
		self.logger.info("[{}] {} event received: {}".format(time.strftime("%H:%M:%S"), event.eventType, event.data))