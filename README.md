# gasmeter

Using a rasperrypi  and a reed contact to log the gas consumption.

     $ python3 -m venv  --system-site-packages  ./venv
     $ venv/bin/pip install -r requirements.txt

Configuration:
```bash
$ cp config.ini.example config.ini
```

Edit 

```ini
[mqtt]
broker = 'openhab'
port = 1883
topic = "test/gas"
username = 'user'
password = 'secret'
```