# gasmeter

Using a rasperrypi  and a reed contact to log the gas consumption.

```bash
$ python3 -m venv  --system-site-packages  ./venv
$ venv/bin/pip install -r requirements.txt
```
Configuration:
```bash
$ cp config.ini.example config.ini
```

Edit 

```ini
[app]
gpio = 27
impulse = 0.01
brennwert = 10.355
zustandszahl = 0.9690

[mqtt]
id = raspi
name = raspi with several sensors
homieversion = 4.0
broker = localhost
port = 1883
username = mosqitto
password = *****
insecure = True
qos = 1
retain_message = True
# Retry to connect to mqtt broker
mqttretry = 5
# how often should be a publish to MQTT (in Seconds)
publishtime = 120
```

# Ref
https://github.com/alaub81/rpi_sensor_scripts
