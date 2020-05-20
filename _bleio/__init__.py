# The MIT License (MIT)
#
# Copyright (c) 2020 Dan Halbert for Adafruit Industries LLC
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.
"""

_bleio implementation for Adafruit_Blinka_bleio

* Author(s): Dan Halbert for Adafruit Industries
"""

import asyncio

from _bleio.adapter import *
from _bleio.address import *
from _bleio.attribute import *
from _bleio.characteristic import *
from _bleio.characteristic_buffer import *
from _bleio.connection import *
from _bleio.exceptions import *
from _bleio.packet_buffer import *
from _bleio.scan_entry import *
from _bleio.scan_results import *
from _bleio.service import *
from _bleio.uuid import *

__version__ = "0.0.0-auto.0"
__repo__ = "https://github.com/adafruit/Adafruit_Blinka_bleio.git"

# Create singleton of adapter as _bleio.adapter
adapter = Adapter()
# enable adapter on import.
adapter.enabled = True

def asyncio_run_in_loop(coro, *, debug=False):
    loop = asyncio.get_event_loop()
    loop.run_until_complete(coro())