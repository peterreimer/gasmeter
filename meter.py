#!/bin/env python3
# -*- coding: utf-8 -*-
# import argparse
import configparser
import csv
import json
import logging
import os
import random
import time

#import config as cfg
from gpiozero import Button
from paho.mqtt import client as mqtt_client

logger = logging.getLogger(__name__)

# Setting up Logging
logger.setLevel(logging.DEBUG)
console = logging.StreamHandler()
formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
console.setFormatter(formatter)
logger.addHandler(console)


latest = "gas.json"

IMP = 0.01
history = {
    'impulses':[],
    'daily':0,
    'total':0
    }

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
REED = Button(gpio)

TIME_FORMAT = '%Y-%m-%dT%H:%M:%S'
NODE = "gascounter"

def read_latest():
    """Get latest value from json file"""
    try:
        f = open(latest, "r")
        data = json.load(f)
        f.close()
        return float(data['volume'])
    except:
        return 0
  

def write_latest(measurement):
    """Save latest value to json file"""
    log = {
        "date": time.strftime(TIME_FORMAT),
        "volume" : measurement
        }
    logger.info(f"write {measurement}")
    f = open(latest, "w")
    f.write(json.dumps(log))
    f.close()

def log_data(measurement):
    log = {
        "date": time.strftime(TIME_FORMAT),
        "volume" : measurement
        }
    year = time.strftime("%Y")
    month = time.strftime("%m")
    day = time.strftime("%d")
    #csv_daily = "%s%s%s.csv" % (year, month, day) 
    csv_daily = f"{year}{month}{day}.csv"  
    log_dir = os.path.join("log", year, month)
    if not os.path.isdir(log_dir):
        os.makedirs(log_dir)
    csv_file = os.path.join(log_dir, csv_daily)
    # add header only when we start a new file on new day
    add_header = False
    if not os.path.isfile(csv_file):
        add_header = True
    with open(csv_file, 'a', newline='') as csvfile:
        fieldnames = log.keys()
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if add_header is True:
            writer.writeheader()
        writer.writerow(log)
    return 3

def keep_history(impulse, daily, total):
    history['impulses'].append(impulse)
    history['daily'] = daily
    history['total'] = total
    print(history)
    

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
    
    properties = "reading, daily, weekly, monthly"
    publish('/'.join([NODE, "$name"]), "Reed contact")
    publish('/'.join([NODE, "$properties"]), properties)
    publish('/'.join([NODE, "reading", "$name"]), "Counter Reading")
    publish('/'.join([NODE, "reading", "$unit"]), "m³")
    publish('/'.join([NODE, "reading", "$datatype"]), "float")
    publish('/'.join([NODE, "reading", "$settable"]), "true")
    # homie state ready
    publish("$state", "ready")


def on_disconnect(client, userdata, rc):
    logger.info(f"MQTT Connection disconnected, Returned code={rc}")


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
    except Exception as error:
        # Possible errors
        # [Errno 113] No route to host
        # [Errno 111] Connection refuse
        wait = 5
        logger.info(f"Could not connect to  MQTT Broker: {error}! Trying again in {mqttretry - mqttattempts}x times after {wait}s")
        mqttattempts += 1
        if mqttattempts == mqttretry:
            logger.info("Could not connect to MQTT Broker! Giving up.")
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
    readout = round(latest_measurement, 3)
    write_latest(readout)
    daily = log_data(readout)
    print(daily)
    #now = time.strftime(TIME_FORMAT)
    #impulses = history["impulses"]
    #if len(impulses) > 0:
    #    print(impulses[-1])
    #print(time.strftime("%w"))
    #keep_history(now, readout, readout)
        
    publish(NODE + "/reading", "{:.2f}".format(readout))
    

# finaly the loop
while True:
    try:
        REED.when_pressed = closed
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
        logger.error("An Error occured ... ")
        time.sleep(3)
        continue

# At least close MQTT Connection
logger.info("Script stopped")
publish("$state", "disconnected")
time.sleep(1)
client.disconnect()
client.loop_stop()
