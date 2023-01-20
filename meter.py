#!/bin/env python3
import argparse
import configparser
import csv
import json
import logging
import os
import random
import time
import sys
from datetime import datetime

from gpiozero import Button
from paho.mqtt import client as mqtt_client

logger = logging.getLogger(__name__)

LOG_DIR = "log"
IMP = 0.01
latest = "gas.json"

# generate client ID with pub prefix randomly
client_id = f'python-mqtt-{random.randint(0, 1000)}'


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
    f = open(latest,"w")
    f.write(log)
    f.close()

def log_to_csv(values):
    """Create an CSV Logfile per day for logging the reading of the gasmeter"""

    dateobj = datetime.fromisoformat(values["date"])
    year = dateobj.strftime("%Y")
    month = dateobj.strftime("%m")
    day = dateobj.strftime("%d")

    csv_daily = "%s%s%s.csv" % (year, month, day)
    data_dir = os.path.join(LOG_DIR, year, month)

    if not os.path.isdir(data_dir):
        os.makedirs(data_dir)
    csv_file = os.path.join(data_dir, csv_daily)
    # add header only when we start a new file on new day
    add_header = False
    if not os.path.isfile(csv_file):
        add_header = True
    
    with open(csv_file, 'a', newline='') as csvfile:
        fieldnames = values.keys()
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        if add_header is True:
            writer.writeheader()
        writer.writerow(values)



def run():

    logger.setLevel(logging.DEBUG)
    console = logging.StreamHandler()
    formatter = logging.Formatter('%(levelname)s: %(message)s')
    console.setFormatter(formatter)
    logger.addHandler(console)

    parser = argparse.ArgumentParser(description='Reading and logging a gasmeter')
    parser.add_argument('-c', '--conf', help='Configuration file', required=True)

    args = parser.parse_args()
    config_file = args.conf

    config = configparser.ConfigParser()

    if os.path.isfile(config_file):
        config.read(config_file)
        # get gasmeter properties
        app = config['app']
        impulse = app.getfloat('impulse', 0.1)

        # get MQTT settings
        mqtt = config['mqtt']
        broker = mqtt.get('broker', '127.0.0.1')
        port = mqtt.getint('port', 1883)
        topic = mqtt.get('topic', '')
        username = mqtt.get('username', '')
        password = mqtt.get('password', '')

        # gpio
        gpio = app.getint('gpio', '')
        reed = Button(gpio)
    else:
        print(f"{config_file} does not exist")
        sys.exit()



    logger.info(f"using MQTT broker at {broker}:{port}")

    def connect_mqtt():
        def on_connect(client, userdata, flags, rc):
            if rc == 0:
                logger.info("Connected to MQTT Broker!")
            else:
                logger.warn(f"Failed to connect, return code {rc}", rc)

        client = mqtt_client.Client(client_id)
        client.username_pw_set(username, password)
        client.on_connect = on_connect
        client.connect(broker, port)
        return client

    def closed():
        """Increase the consumption value for each closing of the reed contact"""
        latest__measurement = read_latest()
        latest__measurement += 1 * IMP
        date = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
        consumption = round(latest__measurement,3)
        measurement = {"date": date, "volume": consumption}
        log_to_csv(measurement)
        log = json.dumps(measurement)
        
        write_latest(log)

        # publish to MQTT Broker
        client = connect_mqtt()
        client.loop_start()
        result = client.publish(topic, log)
        # result: [0, 1]
        status = result[0]
        logger.debug(status)
        if status == 0:
            logger.info(f"Send `{log}` to topic `{topic}`")
        else:
            logger.info(f"Failed to send message to topic {topic}")
        client.disconnect()

    while True:
        reed.when_pressed = closed
        time.sleep(0.1)


if __name__ == '__main__':
    run()
