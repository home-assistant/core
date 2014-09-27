FROM python:3-onbuild
MAINTAINER Paulus Schoutsen <Paulus@PaulusSchoutsen.nl>

RUN git clone https://github.com/studioimaginaire/phue.git

VOLUME /config

EXPOSE 8123

CMD [ "python", "./start.py", "--docker" ]
