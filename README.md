# purr - CircuitPython remote access (alternative to ampy)

I wrote `purr` mainly to explore a different design than `ampy` used for
remote access, and to see whether the result was any faster or more reliable.
There are two main differences.  First, I believe the sequence used to
break out of `main.py` into the repl is a bit more robust.  Second, I use a
remote stub program, which allows a bit more sophisticated communication
between local and remote systems—Any `repr()`able object can be transmitted,
and 8-bit-cleanliness for get/put operations is easy to achieve.

However, `purr` is not anywhere near as mature as `ampy`, and while it
works well enough for me to share it with others, it's probably not ready
for daily use.

At this time, purr is only tested on Debian Stable with Python 3.5.3.  The
remote board for most testing has been a Feather HUZZAH 8266 with CircuitPython
2.x.  Other boards probably do not have the required `ubinascii` and `uhashlib`
modules.

# Installation

```
$ python3 setup.py install --user
```

# Commandline use

```
$ purr -p /dev/ttyUSB0 cat /main.py
$ purr --help
```

`purr` will start up somewhat faster if you permanently upload the stub, but it
consumes around 3000 bytes of storage.

```
$ purr -p /dev/ttyUSB0 maint upload_stub
```

# Use in another Python program

Connect to a board:

```
$ python3
>>> import purr.board
>>> p = purr.board.purr_serial("/dev/ttyUSB0")
```

Run a command remotely:

```
>>> p.exec("print(42)")
INFO:root:Remote: 42
```

Evaluate code remotely and return a result (works for any `repr()`able value):

```
>>> p.exec("import board")
>>> p.eval("dir(board)")
['ADC', 'GPIO16', 'GPIO14', 'SCK', 'GPIO12', 'MISO', 'GPIO13', 'MOSI', 'GPIO15', 'GPIO2',
 'GPIO0', 'GPIO4', 'SDA', 'RX', 'TX', 'GPIO5', 'SCL']
```

Remote exceptions are converted into local exceptions, though the type information and remote traceback are lost:

```
>>> p.eval("1/0")
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
  File "…/purr/board.py", line 114, in eval
    return self.send_purr_command('eval', s)
  File "…/purr/board.py", line 108, in send_purr_command
    raise PurrError(result[1])
purr.board.PurrError: division by zero
```

Non-`repr()`able values fail, and the error message can be deceptive:

```
>>> p.exec("import os")
>>> p.eval("os.uname()")
Traceback (most recent call last):
  File "<stdin>", line 1, in <module>
  File "…/purr/board.py", line 114, in eval
    return self.send_purr_command('eval', s)
  File "…/purr/board.py", line 106, in send_purr_command
    result = eval(result)
  File "<string>", line 1
    (True, (sysname='esp8266', nodename='esp8266', release='2.2.0-dev(9422289)', version='2.2.4-4-g1062e193e on 2018-04-06', machine='ESP module with ESP8266'))
                   ^
SyntaxError: invalid syntax
```

## purr.commands - handy utilities

```
>>> import purr.commands
>>> content = purr.commands.getfile(p, '/main.py')
>>> print((len(content), hashlib.sha256(content).hexdigest()))
(2505, '91b62...')
>>> print(purr.commands.checksum(p, "/main.py"))    # computes checksum remotely
(2505, b'91b62...')
```

## purr.commands.remote - decorator for easy remote execution
(note: `@purr.commands.remote` doesn't work in the python repl, you have to apply it to a function within a main file or an imported module)

For instance, a wrapper for `os.uname()`, since `os.uname()`'s value is not `repr()`able:
```
#mycommands.py
import purr.commands

@purr.commands.remote
def uname(stub):
    import os
    return tuple(os.uname())
```

```
>>> import mycommands
>>> mycommands.uname(p)
('esp8266', 'esp8266', '2.2.0-dev(9422289)', '2.2.4-4-g1062e193e on 2018-04-06', 'ESP module with ESP8266')
```

Within a purr session, all the `@purr.commands` must have distinct unqualified
names.  Failure to do so will cause the wrong command to be executed.
