#!/usr/bin/env python

'''
https://sigrok.org/wiki/RDTech_UM24C

All data returned by the device consists of measurements and configuration status, in 130-byte chunks. To my knowledge, it will never send any other data. All bytes below are displayed in hex format; every command is a single byte.

# Commands to send:
F0 - Request new data dump; this triggers a 130-byte response
F1 - (device control) Go to next screen
F2 - (device control) Rotate screen
F3 - (device control) Switch to next data group
F4 - (device control) Clear data group
Bx - (configuration) Set recording threshold to a value between 0.00 and 0.15 A (where 'x' in the byte is 4 bits representing the value after the decimal point, eg. B7 to set it to 0.07 A)
Cx - (configuration) Same as Bx, but for when you want to set it to a value between 0.16 and 0.30 A (16 subtracted from the value behind the decimal point, eg. 0.19 A == C3)
Dx - (configuration) Set device backlight level; 'x' must be between 0 and 5 (inclusive)
Ex - (configuration) Set screen timeout ('screensaver'); 'x' is in minutes and must be between 0 and 9 (inclusive), where 0 disables the screensaver

# Response format:
All byte offsets are in decimal, and inclusive. All values are big-endian and unsigned.
0   - 1   Start marker (always 0x0963)
2   - 3   Voltage (in mV, divide by 1000 to get V)
4   - 5   Amperage (in mA, divide by 1000 to get A)
6   - 9   Wattage (in mW, divide by 1000 to get W)
10  - 11  Temperature (in celsius)
12  - 13  Temperature (in fahrenheit)
14        Unknown (not used in app)
15        Currently selected data group
16  - 95  Array of main capacity data groups (where the first one, group 0, is the ephemeral one)
            -- for each data group: 4 bytes mAh, 4 bytes mWh
96  - 97  USB data line voltage (positive) in centivolts (divide by 100 to get V)
98  - 99  USB data line voltage (negative) in centivolts (divide by 100 to get V)
100       Charging mode; this is an enum, where 0 = unknown/standard, 1 = QC2.0, and presumably 2 = QC3.0 (but I haven't verified this)
101       Unknown (not used in app)
102 - 105 mAh from threshold-based recording
106 - 109 mWh from threshold-based recording
110 - 111 Currently configured threshold for recording
112 - 115 Duration of recording, in seconds since start
116       Recording active (1 if recording)
117       Unknown (not used in app)
118 - 119 Current screen timeout setting
120 - 121 Current backlight setting
122 - 125 Resistance in deci-ohms (divide by 10 to get ohms)
126       Unknown
127       Current screen (same order as on device)
128 - 129 Stop marker (always 0xfff1)
'''

'''
on archlinux:
sudo pacman -Sy bluez bluez-firmware bluez-utils bluez-tools python-pybluez
sudo systemctl start bluetooth
sudo bluetoothctl
# power on
# scan on
# pair ###BTADDR###
# trust ###BTADDR###
./um25c_bluetooth_receiver.py ###BTADDR###
{'voltage': 0.496, 'current': 0.17, 'power': 0.843, 'temp_celsius': 28, 'temp_fahrenheit': 82, 'usb_data_pos_voltage': 0.62, 'usb_data_neg_voltage': 0.62, 'charging_mode': 0}
...
'''

import bluetooth
import struct
import time

def connect_to_usb_tester(bt_addr):
    sock = bluetooth.BluetoothSocket(bluetooth.RFCOMM)
    sock.connect((bt_addr, 1))
    sock.settimeout(1.0)
    for _ in range(10):
        try:
            read_data(sock)
        except bluetooth.BluetoothError as e:
            time.sleep(0.2)
        else:
            break
    else:
        raise e
    return sock

def read_data(sock):
    sock.send(bytes([0xF0]))
    d = bytes()
    while len(d) < 130:
        d += sock.recv(1024)
    assert len(d) == 130, len(d)
    return d

def read_measurements(sock):
    d = read_data(sock)
    assert d[0:2] == bytes([0x09, 0x63])
    assert d[-2:] == bytes([0xff, 0xf1])
    voltage, current, power = [x/1000 for x in struct.unpack('!HHI', d[2:10])]
    temp_celsius, temp_fahrenheit = struct.unpack('!HH', d[10:14])
    usb_data_pos_voltage, usb_data_neg_voltage = [x/100 for x in struct.unpack('!HH', d[96:100])]
    charging_mode = d[100]
    del d
    del sock
    return locals()

if __name__ == '__main__':
    import sys
    bt_addr = sys.argv[1]
    sock = connect_to_usb_tester(bt_addr)
    try:
        try:
            while True:
                print(read_measurements(sock))
        except KeyboardInterrupt:
            pass
    finally:
        sock.close()

