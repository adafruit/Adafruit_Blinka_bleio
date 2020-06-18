Introduction
============

.. image:: https://readthedocs.org/projects/adafruit-blinka-bleio/badge/?version=latest
    :target: https://circuitpython.readthedocs.io/projects/blinka_bleio/en/latest/
    :alt: Documentation Status

.. image:: https://img.shields.io/discord/327254708534116352.svg
    :target: https://discord.gg/nBQh6qu
    :alt: Discord

.. image:: https://github.com/adafruit/Adafruit_Blinka_bleio/workflows/Build%20CI/badge.svg
    :target: https://github.com/adafruit/Adafruit_Blinka_bleio/actions
    :alt: Build Status

`_bleio` for Blinka based on `bleak <https://github.com/hbldh/bleak>`_ and bluez.


Dependencies
=============
This driver depends on:

* `bleak <https://github.com/hbldh/bleak>`_

It optionally also depends on these Debian packages not install on Raspbian by default:

* ``bluez-hcidump``

Installing from PyPI
=====================

On supported GNU/Linux systems like the Raspberry Pi, you can install the driver locally `from
PyPI <https://pypi.org/project/adafruit-blinka-bleio/>`_. To install for current user:

.. code-block:: shell

    pip3 install adafruit-blinka-bleio

To install system-wide (this may be required in some cases):

.. code-block:: shell

    sudo pip3 install adafruit-blinka-bleio

To install in a virtual environment in your current project:

.. code-block:: shell

    mkdir project-name && cd project-name
    python3 -m venv .env
    source .env/bin/activate
    pip3 install adafruit-blinka-bleio


Support for Duplicate Advertisement scanning on Linux
=====================================================

.. note::
   Read this section if you are using advertising to transmit changing
   data and need to receive all advertisements to receive this data.
   One example of using advertising for data is described in the Adafruit Learn Guide
   `Bluetooth LE Sensor Nodes to Raspberry Pi WiFi Bridge
   <https://learn.adafruit.com/bluetooth-le-broadcastnet-sensor-node-raspberry-pi-wifi-bridge>`_.

The regular Linux kernel ``bluez`` driver is set up to suppress
multiple advertisements sent from the same BLE device.  As of this
writing, this cannot be changed.  If you are using BLE advertisements
to send changing data that you retrieve by scanning, the
de-duplication can cause you to lose data when scanning via ``bleak``.

To get around this problem, this library can instead look at raw BLE
scanning data using the ``hcidump`` and ``hcitool`` tools and avoid
going through the kernel driver. But this requires special setup.

Normally, only root has enough privileges to do see the raw scanning
data.  Since running as root is dangerous, you can instead use Linux
capabilities to grant ``hcitool`` and ``hcidump`` raw network
access. This is very powerful and not something to do casually. To
limit access we recommend you change file execution permissions to
restrict this capability to users in the ``bluetooth`` group.

**If you are not using advertising to transmit changing data, you do
not need to add these permissions. This library falls back to using**
``bleak`` **for regular scanning if** ``hcitool`` **does not have
these extra permissions.**

To add yourself to the ``bluetooth`` group do:

.. code-block:: shell

    sudo usermod -a -G bluetooth <your username>

You must then logout and log back in to be in the new group.

To set permissions on ``hcitool`` and ``hcidump`` do:

.. code-block:: shell

    sudo chown :bluetooth /usr/bin/hcitool /usr/bin/hcidump
    sudo chmod o-x /usr/bin/hcitool /usr/bin/hcidump
    sudo setcap 'cap_net_raw,cap_net_admin+eip' /usr/bin/hcitool
    sudo setcap 'cap_net_raw,cap_net_admin+eip' /usr/bin/hcidump

Usage Example
=============

Do not use this library directly. Use CircuitPython BLE instead:
https://github.com/adafruit/Adafruit_CircuitPython_BLE/

Contributing
============

Contributions are welcome! Please read our `Code of Conduct
<https://github.com/adafruit/Adafruit_Blinka_bleio/blob/master/CODE_OF_CONDUCT.md>`_
before contributing to help this project stay welcoming.

Documentation
=============

For information on building library documentation, please check out `this guide <https://learn.adafruit.com/creating-and-sharing-a-circuitpython-library/sharing-our-docs-on-readthedocs#sphinx-5-1>`_.

Troubleshooting
================

Raspberry Pi 3b Rev 1.2
^^^^^^^^^^^^^^^^^^^^^^^^

The Raspberry Pi 3b's BLE chip is connected over UART to the main processor without flow control.
This can cause unreliability with BLE. To improve reliability, we can slow the UART. To do so,
edit ``/usr/bin/btuart`` and replace the ``921600`` with ``460800``.
