import threading
import urlparse

import requests

from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer

SERVER_HOST= '127.0.0.1'
SERVER_PORT = 8080

class RequestHandler(BaseHTTPRequestHandler):
	
	#Handler for the GET requests
	def do_GET(self):
		if self.path == "/":
			self.send_response(200)
			self.send_header('Content-type','text/html')
			self.end_headers()
			
			write = self.wfile.write

			# Describe state machine:
			categories = []

			write("<table>")
			write("<tr><th>Name</th><th>State</th><th>Last Changed</th></tr>")

			for category, state, last_changed in self.server.statemachine.get_states():
				categories.append(category)

				write("<tr><td>{}</td><td>{}</td><td>{}</td></tr>".format(category, state, last_changed.strftime("%H:%M:%S %d-%m-%Y")))

			write("</table>")

			# Small form to change the state
			write("<br />Change state:<br />")
			write("<form action='change_state' method='POST'>")
			write("<select name='category'>")

			for category in categories:
				write("<option>{}</option>".format(category))

			write("</select>")

			write("<input name='new_state' />")
			write("<input type='submit' value='set state' />")
			write("</form>")

		else:
			self.send_response(404)


	def do_POST(self):
		length = int(self.headers['Content-Length'])
		post_data = urlparse.parse_qs(self.rfile.read(length))

		if self.path == "/change_state":
			self.server.statemachine.set_state(post_data['category'][0], post_data['new_state'][0])

			self.send_response(301)
			self.send_header("Location", "/")
			self.end_headers()

		else:
			self.send_response(404)


class HttpInterface(threading.Thread):

	def __init__(self, eventbus, statemachine):
		threading.Thread.__init__(self)

		self.server = HTTPServer((SERVER_HOST, SERVER_PORT), RequestHandler)

		self.server.eventbus = eventbus
		self.server.statemachine = statemachine

		self._stop = threading.Event()


	def run(self):		
		while not self._stop.is_set():
			self.server.handle_request()

	def stop(self):
		self._stop.set()

		# Trigger a fake request to get the server to quit
		requests.get("http://{}:{}".format(SERVER_HOST, SERVER_PORT))