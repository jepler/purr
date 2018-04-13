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

try:
    import binascii
except:
    import ubinascii as binascii
    
try:
    import os
except:
    import uos as os

import sys

class RemoteStub:
    def __init__(self, f_in=sys.stdin, f_out=sys.stdout):
        self.f_in = getattr(f_in, 'buffer', f_in)
        self.f_out = getattr(f_out, 'buffer', f_out)
        self.state = {}

    def eval(self, s): return eval(s, globals(), self.state)

    def exec(self, s): return exec(s, globals(), self.state)

    def putb64(self, s):
        self.f_out.write(b"__STUB__\n")
        mv = memoryview(s)
        for i in range(0, len(s), 90):
            v = mv[i:i+90]
            self.f_out.write(binascii.b2a_base64(v))
        self.f_out.write(b"~~STUB~~\n")

    def getb64g(self):
        while 1:
            line = self.f_in.readline().strip()
            if line == b'__STUB__':
                self.f_out.write(".")
                break
        while 1:
            line = self.f_in.readline().strip()
            if line == b'~~STUB~~':
                self.f_out.write("\n")
                break
            self.f_out.write(".")
            yield binascii.a2b_base64(line)

    def getb64(self):
        return b"".join(self.getb64g())

    def getfunction(self, function):
        if '.' in function:
            module_name, function = function.rsplit('.', 1)
            try:
                obj = __import__(module_name)
            except:
                obj = __import__('u' + module_name)
        else:
            obj = self
        return getattr(obj, function)

    def loop(self):
        self.putb64(b'')
        while 1:
            function = self.getb64()
            if function == b'exit':
                return
            args = self.getb64()

            try:
                function = self.getfunction(function.decode('ascii'))
                args = eval(args)
                result = True, function(*args)
            except Exception as e:
                result = False, e
            if result[0] and type(result[1]).__name__ == 'generator':
                self.putb64(repr('generator'))
                try:
                    for i in result[1]:
                        self.putb64(repr((True, i)))
                except Exception as e:
                    self.putb64((False, e))
                    return
                self.putb64(repr(None))
            else:
                self.putb64(repr(result))

    def rfunc(self, fname, *args): return self.state[fname](self, *args)
