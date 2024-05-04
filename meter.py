#!/bin/env python3
# -*- coding: utf-8 -*-
import argparse
import configparser
import csv
import json
import logging
import os
import random
import time

from gpiozero import Button
from paho.mqtt import client as mqtt_client
from systemd.daemon import notify, Notification

logger = logging.getLogger(__name__)

# Setting up Logging
logger.setLevel(logging.DEBUG)
console = logging.StreamHandler()
#formatter = logging.Formatter('%(asctime)s %(levelname)s: %(message)s')
formatter = logging.Formatter('%(levelname)s: %(message)s')
console.setFormatter(formatter)
logger.addHandler(console)

latest = "gas.json"

parser = argparse.ArgumentParser(description='Manages DOIs at Data')
parser.add_argument('-c', '--conf',
					 help='Configuration file with access data')

args = parser.parse_args()
if args.conf:
    config_file = args.conf
else:
    config_file = "config.ini"
    
logger.info(f"config:  {config_file}")

history = {
    'impulses':[],
    'daily':0,
    'total':0
    }

# generate client ID with pub prefix randomly
client_id = f'python-mqtt-{random.randint(0, 1000)}'

config = configparser.ConfigParser()
config.read(config_file)

app = config['app']
gpio = app.getint('gpio', '')
impulse = app.getfloat('impulse', 1.0)
brennwert = app.getfloat('brennwert', 10.0)
zustandszahl = app.getfloat('zustandszahl', 1.0)

logger.info(f"GPIO:  {gpio}")
logger.info(f"IMP:  {impulse}")
logger.info(f"Brennwert: {brennwert}")
logger.info(f"Zustandszahl: {zustandszahl}")

# get MQTT settings
mqtt = config['mqtt']
broker = mqtt.get('broker', '127.0.0.1')
port = mqtt.getint('port', 1883)
id = mqtt.get('id', '')
name = mqtt.get('name', '')
username = mqtt.get('username', '')
password = mqtt.get('password', '')
insecure = mqtt.getboolean('insecure', True)
qos = mqtt.getint('qos', 0)
retain_message = mqtt.getboolean('retain_message', True)
mqttretry = mqtt.getint('mqttretry', 2)
publishtime = mqtt.getint('publishtime', 600)
homieversion = mqtt.get('homieversion', 4.0)
logger.info(f"QoS:  {qos}")

# GPIO
gpio = app.getint('gpio', '')
REED = Button(gpio)

TIME_FORMAT = '%Y-%m-%dT%H:%M:%S'

def read_latest():
    """Get latest value from json file"""
    try:
        f = open(latest, "r")
        data = json.load(f)
        f.close()
        return float(data['total']), float(data['daily'])
    except:
        return 0, 0


def write_latest(total, daily):
    """Save latest value to json file"""
    log = {
        "date": time.strftime(TIME_FORMAT),
        "total" : total,
        "daily" : daily
        }
    log = {
        "date": time.strftime(TIME_FORMAT),
        "total" : total,
        "daily" : daily
        }
    f = open(latest, "w")
    f.write(json.dumps(log))
    f.close()

def process_data():
    """Calculate and return current reading and consumption"""

    # setting up log file
    year = time.strftime("%Y")
    month = time.strftime("%m")
    day = time.strftime("%d")
    csv_daily = f"{year}{month}{day}.csv"  
    log_dir = os.path.join("log", year, month)
    if not os.path.isdir(log_dir):
        os.makedirs(log_dir)
    csv_file = os.path.join(log_dir, csv_daily)
    if not os.path.isfile(csv_file):
        new_day = True
    else:
        new_day = False

    # total counter
    total, daily = read_latest()
    if new_day:
        daily = 0.0
    total += 1 * impulse
    total = round(total, 2)
    
    daily += 1 * impulse * brennwert * zustandszahl
    daily = round(daily, 3)
    write_latest(total, daily)

    log = {
        "date": time.strftime(TIME_FORMAT),
        "total" : total,
        "daily" : daily
        }
    
    # add header only when we start a new file on new day
    
    if new_day:
        add_header = True
    else:
        add_header = False

    with open(csv_file, 'a', newline='') as csvfile:
        fieldnames = log.keys()
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if add_header is True:
            writer.writeheader()
        writer.writerow(log)
    return total, daily

#def keep_history(impulse, daily, total):
#    history['impulses'].append(impulse)
#    history['daily'] = daily
#    history['total'] = total
    

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
    publish("$nodes", "gasmeter")
    publish("$nodes", "gasmeter")
    # homie node config
    node = "gasmeter"
    properties = "total,daily"
    node = "gasmeter"
    properties = "total,daily"
    publish('/'.join([node, "$name"]), "Reed contact")
    publish('/'.join([node, "$properties"]), properties)
    publish('/'.join([node, "total", "$name"]), "Counter Reading")
    publish('/'.join([node, "total", "$unit"]), "m³")
    publish('/'.join([node, "total", "$datatype"]), "float")
    publish('/'.join([node, "total", "$settable"]), "true")
    publish('/'.join([node, "daily", "$name"]), "Daily Consumption")
    publish('/'.join([node, "daily", "$unit"]), "kWh")
    publish('/'.join([node, "daily", "$datatype"]), "float")
    publish('/'.join([node, "total", "$name"]), "Counter Reading")
    publish('/'.join([node, "total", "$unit"]), "m³")
    publish('/'.join([node, "total", "$datatype"]), "float")
    publish('/'.join([node, "total", "$settable"]), "true")
    publish('/'.join([node, "daily", "$name"]), "Daily Consumption")
    publish('/'.join([node, "daily", "$unit"]), "kWh")
    publish('/'.join([node, "daily", "$datatype"]), "float")
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
notify(Notification.READY)

client.on_connect = on_connect
client.on_disconnect = on_disconnect


def closed():
    """Increase the consumption value for each closing of the reed contact"""
    total, daily = process_data()
    logger.info(f"total {total} m³, daily {daily} kWh")
    node = "gasmeter"    
    #publish(node + "/total", "{:.2f}".format(total))
    #publish(node + "/daily", "{:.3f}".format(daily))
    publish("/".join([node, "total"]), total)
    publish("/".join([node, "daily"]), daily)
    

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
