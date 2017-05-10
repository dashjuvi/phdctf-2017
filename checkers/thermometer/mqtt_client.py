#!/usr/bin/env python3

import sys
import datetime
import paho.mqtt.client as mqtt
from paho.mqtt.client import connack_string
import time
import signal

OK, CORRUPT, MUMBLE, DOWN, CHECKER_ERROR = 101, 102, 103, 104, 110

def trace(public="", private=""):
    if public:
        print(public)
    if private:
        print(private, file=sys.stderr)



class MqttClient:
    def __init__(self, host):
        self._broker_host = host
        self._mqtt_client = mqtt.Client()
        self._check_result = DOWN

    def handle_timeout(self, signum, frame):
        trace("Timeout", "Connection timeout.")
        raise TimeoutError("Connection timeout.")

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            self._check_result = OK
            self._mqtt_client.disconnect()
        else:
            trace("Connection to MQTT broker refused", "Connection to MQTT broker refused (code=%d): %s." % (rc, connack_string(rc)))
            self._check_result = DOWN

    def check_connect(self):
        try:
            self._mqtt_client.on_connect = self.on_connect

            signal.signal(signal.SIGALRM, self.handle_timeout)
            signal.alarm(4)

            try:
                self._mqtt_client.connect(self._broker_host, 1883, keepalive=10)
                self._mqtt_client.loop_forever()
            except TimeoutError:
                return DOWN
            except Exception as e:
                trace("Connection error", "Connection error: %s" % e)
                return DOWN

            if self._check_result != OK:
                trace("Timeout", "Timeout at MqttClient.check_connect()")
            return self._check_result

        except Exception as e:
            trace("Unknown error", "Unknown request error: %s" % e)
            return CHECKER_ERROR
