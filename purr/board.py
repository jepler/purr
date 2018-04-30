# CircuitPython remote access
# Copyright © 2018 Jeff Epler <jepler@gmail.com>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from __future__ import absolute_import, print_function, division
import binascii
import pkg_resources
import serial
import logging
import os
import time

rstub_src = pkg_resources.resource_string(__package__ or __name__, 'rstub.py')

if not hasattr(time, 'monotonic'):
    time.monotonic = time.time

PURR_STATE_UNKNOWN, PURR_STATE_PURR, PURR_STATE_REPL, PURR_STATE_RAW_REPL, PURR_STATE_RUN = range(5)

class PurrError(Exception): pass
class TimeoutError(PurrError): pass

class PurrBoard:
    def __init__(self, comm):
        self.state = PURR_STATE_UNKNOWN
        self.comm = comm

    def do_write(self, data):
        """Write data to the attached device in blocking mode"""
        return self.comm.write(data)

    def do_read_deadline(self, min_bytes, t_end):
        """Read data from attached device subject to an end time
        If t_end is in the past (including zero, perform a pure nonblocking read"""
        return self.comm.read_deadline(min_bytes, t_end)

    def read_deadline(self, min_bytes=1, timeout=0, t_end=None):
        t_end = t_end or time.monotonic() + timeout
        return self.do_read_deadline(min_bytes, t_end)

    def drain(self):
        while self.read_deadline(timeout=.1): pass

    def write(self, data, chunksize=128):
        for i in range(0, len(data), chunksize):
            if i: time.sleep(.02)
            self.do_write(data[i:i+chunksize])

    def read_until(self, ending, *, timeout=2, t_end=0, consumer=lambda s: None):
        t_end = t_end or time.monotonic() + timeout
        data = b''
        while 1:
            new_data = self.read_deadline(t_end=t_end)
            if not new_data: break
            data += new_data
            consumer(new_data)
            if data.endswith(ending):
                break
        if data: logging.debug("read_until(%r) ->%r %r", ending, data.endswith(ending), data)
        return data

    def readline(self, timeout=2, t_end=0):
        return self.read_until(b'\n', timeout=timeout, t_end=t_end)

    def putb64(self, s):
        self.write(b"\n__STUB__\n");
        if not isinstance(s, bytes): s = s.encode('utf-8')
        mv = memoryview(s)
        for i in range(0, len(s), 90):
            v = mv[i:i+90]
            self.write(binascii.b2a_base64(v))
            self.read_until(b'.')
        self.write(b"~~STUB~~\n"); self.read_until(b'\n')

    def getb64g(self):
        while 1:
            line = self.readline().rstrip()
            if line.endswith(b'__STUB__'):
                break
            logging.info("Remote: %s", (line.decode('ascii', 'replace')))
        while 1:
            line = self.readline().strip()
            if line == b'~~STUB~~':
                break
            yield binascii.a2b_base64(line)

    def getb64(self):
        return b"".join(self.getb64g())
    
    def remote_generator_to_list(self):
        r = []
        while 1:
            result = self.getb64()
            result = eval(result)
            if result is None:
                break # StopIteration
            if result[0]:
                r.append(result[1])
            else:
                raise PurrError(result[1])
        return r

    def send_purr_command(self, fun, *args):
        self.enter_purr()
        self.putb64(repr((fun, args)).encode('utf-8'))
        result = self.getb64()
        result = eval(result)
        if result == 'generator':
            return self.remote_generator_to_list()
        if result[0]: return result[1]
        raise PurrError(result[1])

    def exec(self, s):
        self.send_purr_command('exec', s)

    def eval(self, s):
        return self.send_purr_command('eval', s)

    def enter_purr(self, *, force=False, timeout=16, t_end=0, softreset=False):
        logging.debug("enter_purr %s %s", force, self.state)
        if self.state == PURR_STATE_PURR and not force: return
        t_end = t_end or time.monotonic() + timeout
        t0 = time.monotonic()
        self.enter_repl(True, t_end=t_end)
        logging.info("enter_repl 1 %fs", time.monotonic()-t0)
        if softreset:
            self.enter_run(True, t_end=t_end)
            logging.info("enter_run  %fs", time.monotonic()-t0)
            self.enter_repl(True, t_end=t_end)
            logging.info("enter_repl 2 %fs", time.monotonic()-t0)
        t1 = time.monotonic()
        logging.info("Mode switching took %fs", t1-t0)

        self.drain()
        self.write(b"RemoteStub\r\n")
        resp = self.read_until(b"\n>>> ")
        logging.debug("result of referring to RemoteStub: %r" % resp)
        if b'Error' in resp:
            self.write(b"from rstub import RemoteStub\r\n")
            resp = self.read_until(b"\n>>> ")
            logging.debug("result of importing: %r" % resp)
        if b'Error' in resp:
            logging.warn("Stub not installed -- consider uploading it with 'purr maint upload_stub' for faster start time")
            self.write(b"\5\r\n");
            t0 = time.monotonic()
            for line in rstub_src.rstrip().split(b"\n"):
                if not line: continue
                if line.startswith(b"#"): continue
                line = line.replace(b"    ", b" ")
                self.read_until(b"===");
                self.write(line + b"\r\n")
            self.write(b"\4");
            self.read_until(b">>>")
            t1 = time.monotonic()
            logging.info("Sending stub took %fs", t1-t0)
        else:
            logging.info("Using preinstalled stub")
        self.write(b"RemoteStub().loop()\r\n")
        self.getb64()
        self.state = PURR_STATE_PURR

    def enter_repl(self, force=False, timeout=16, t_end=0):
        logging.debug("enter_repl %s %s", force, self.state)
        if self.state == PURR_STATE_REPL and not force: return
        t_end = t_end or time.monotonic() + timeout
        
        while time.monotonic() < t_end:
            self.drain()
            self.write(b"\2\3")
            data = self.read_until(b"\n>>> ", t_end=min(time.monotonic() + 1, t_end))
            if data.endswith(b"\n>>> "): break
            time.sleep(.01)
        else:
            raise TimeoutError
        self.state = PURR_STATE_REPL

    def enter_raw_repl(self, force=False, timeout=16, t_end=0):
        logging.debug("enter_raw_repl %s %s", force, self.state)
        if self.state == PURR_STATE_RAW_REPL and not force: return
        t_end = t_end or time.monotonic() + timeout
        self.enter_repl(force, timeout)
        while time.monotonic() < t_end:
            self.drain()
            self.write(b"\3\1")
            data = self.read_until(b"CTRL-B to exit\r\n>", timeout=min(time.monotonic() + 1, t_end))
            if data.endswith(b"CTRL-B to exit\r\n>"): break
            time.sleep(.01)
        else:
            raise TimeoutError
        self.state = PURR_STATE_RAW_REPL

    def enter_run(self, force=False, timeout=16, t_end=0):
        logging.debug("enter_run %s %s", force, self.state)
        if self.state == PURR_STATE_RUN and not force: return
        t_end = t_end or time.monotonic() + timeout
        self.enter_repl(self, force, t_end=t_end)
        self.write(b"\n\4")
        self.state = PURR_STATE_RUN

class CommSerial:
    def __init__(self, port, rate=115200):
        self.serial = serial.serial_for_url(port, rate, interCharTimeout=1)

    def read_deadline(self, min_bytes, t_end):
        data = b''
        while len(data) < min_bytes:
            t = time.monotonic()
            if t > t_end: break
            self.serial.timeout = t_end-t
            new_data = self.serial.read(min_bytes - len(data))
            data += new_data
        return data

    def write(self, data):
        logging.debug("WRITE %r", data)
        self.serial.write(data)

def purr_serial(port, rate=115200):
    return PurrBoard(CommSerial(port, rate))
