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

It also depends on these Debian packages not install on Raspbian by default:

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

Permissions
=============

For comprehensive scanning we use ``hcidump`` and ``hcitool``. By default, only root has
enough privileges to do what we need.

So, to get permissions we use capabilities to grant ``hcitool`` and ``hcidump`` raw network
access. This is very powerful! So, to limit access we change file execution permissions to
restrict it to users in the bluetooth group.

To add your user to the bluetooth group do:

.. code-block:: shell

    sudo usermod -a -G bluetooth <your username>

To set permissions do:

.. code-block:: shell

    sudo chown :bluetooth /usr/bin/hci*
    sudo chmod o-x /usr/bin/hci*
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
