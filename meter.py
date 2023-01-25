#!/bin/env python3
# -*- coding: utf-8 -*-
# import argparse
import configparser
import json
import logging
import random
import time

from gpiozero import Button
from paho.mqtt import client as mqtt_client

logger = logging.getLogger(__name__)

# Setting up Logging
logger.setLevel(logging.DEBUG)
console = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
console.setFormatter(formatter)
logger.addHandler(console)


IMP = 0.01
latest = "gas.json"


# generate client ID with pub prefix randomly
client_id = f'python-mqtt-{random.randint(0, 1000)}'

config_file = "config.ini"
config = configparser.ConfigParser()
config.read(config_file)

app = config['app']
gpio = app.getint('gpio', '')
logger.info(f"GPIO {gpio}")

# get MQTT settings
mqtt = config['mqtt']
broker = mqtt.get('broker', '127.0.0.1')
port = mqtt.getint('port', 1883)
id = mqtt.get('id', '')
name = mqtt.get('name', '')
nodes = mqtt.get('nodes', '')
username = mqtt.get('username', '')
password = mqtt.get('password', '')
insecure = mqtt.getboolean('insecure', True)
qos = mqtt.getint('qos', 0)
retain_message = mqtt.getboolean('retain_message', True)
mqttretry = mqtt.getint('mqttretry', 2)
publishtime = mqtt.getint('publishtime', 600)
homieversion = mqtt.get('homieversion', 4.0)

# GPIO
gpio = app.getint('gpio', '')
reed = Button(gpio)

# we only have on node, thus it is identical to nodes
node = "reed"
properties = "counter"


def read_latest():
    """Get latest value from json file"""
    try:
        f = open(latest, "r")
        data = json.load(f)
        f.close()
        return data['volume']
    except:
        return 0
  

def write_latest(log):
    """Save latest value to json file"""
    f = open(latest, "w")
    f.write(log)
    f.close()


def publish(topic, payload):
    client.publish("homie/" + id + "/" + topic, payload, qos, retain_message)


def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info(f"MQTT Connection established, returned code={rc}")
        logger.info(f"Publishing every {publishtime} s")
    else:
        logger.warning(f"MQTT Connection failed, returned code={rc}")

    # homie client config
    publish("$state", "init")
    publish("$homie", homieversion)
    publish("$name", name)
    publish("$nodes", nodes)
    # homie node config
    publish('/'.join([node, "$name"]), "Reed contact")
    publish('/'.join([node, "$properties"]), properties)
    publish('/'.join([node, "counter", "$name"]), "Counter Reading")
    publish('/'.join([node, "counter", "$unit"]), "m³")
    publish('/'.join([node, "counter", "$datatype"]), "float")
    publish('/'.join([node, "counter", "$settable"]), "true")
    # homie state ready
    publish("$state", "ready")


def on_disconnect(client, userdata, rc):
    logger.info(f"MQTT Connection disconnected, Returned code={rc}")


def sensorpublish():
    publish(node + "/counter", "{:.1f}".format(counter))
  

# MQTT Connection
mqttattempts = 0
while mqttattempts < mqttretry:
    try:
        client = mqtt_client.Client(client_id)
        client.username_pw_set(username, password)
        # client.tls_set(cert_reqs=ssl.CERT_NONE) #no client certificate needed
        # client.tls_insecure_set(insecure)
        client.will_set('/'.join(["homie", id, "$state"]), "lost", qos, retain_message)
        client.connect(broker, port)
        client.loop_start()
        mqttattempts = mqttretry
    except:
        wait = 5
        logger.info(f"Could not establish MQTT Connection! Try again {mqttretry - mqttattempts}x times after {wait}s")
        mqttattempts += 1
        if mqttattempts == mqttretry:
            logger.info("Could not connect to MQTT Broker! exit...")
            exit(0)
        time.sleep(wait)

# Tell systemd that our service is ready
# systemd.daemon.notify('READY=1')

client.on_connect = on_connect
client.on_disconnect = on_disconnect


def closed():
    """Increase the consumption value for each closing of the reed contact"""

    latest_measurement = read_latest()
    latest_measurement += 1 * 0.01
    consumption = round(latest_measurement, 3)

    measurement = {"volume": consumption}
    
    log = json.dumps(measurement)
    write_latest(log)

    publish(node + "/counter", "{:.2f}".format(consumption))
    logger.info(consumption)

# finaly the loop
while True:
    try:
        reed.when_pressed = closed
        time.sleep(0.1)
    except KeyboardInterrupt:
        logger.info("Goodbye!")
        # At least close MQTT Connection
        publish("$state", "disconnected")
        time.sleep(1)
        client.disconnect()
        client.loop_stop()
        exit(0)

    except:
        logger.error("An Error accured ... ")
        time.sleep(3)
        continue

# At least close MQTT Connection
logger.info("Script stopped")
publish("$state", "disconnected")
time.sleep(1)
client.disconnect()
client.loop_stop()
