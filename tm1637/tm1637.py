"""
TM1637 Library for Raspberry Pi 5 using gpiod (GPIO Daemon)

Modified by: villeparamio
Original Python port: https://github.com/depklyon/raspberrypi-tm1637
Based on MicroPython TM1637 driver: https://github.com/mcauser/micropython-tm1637
License: MIT
"""

from time import sleep
import gpiod
import os

TM1637_CMD1 = 0x40
TM1637_CMD2 = 0xC0
TM1637_CMD3 = 0x80
TM1637_DSP_ON = 0x08
TM1637_DELAY = 0.00001
TM1637_MSB = 0x80

_SEGMENTS = bytearray(
    b'\x3F\x06\x5B\x4F\x66\x6D\x7D\x07\x7F\x6F\x77\x7C\x39\x5E\x79\x71'
    b'\x3D\x76\x06\x1E\x76\x38\x55\x54\x3F\x73\x67\x50\x6D\x78\x3E\x1C'
    b'\x2A\x76\x6E\x5B\x00\x40\x63'
)

def find_gpiochip_for_line(line_offset):
    for chip_path in sorted(os.listdir("/dev")):
        if chip_path.startswith("gpiochip"):
            try:
                chip = gpiod.Chip(f"/dev/{chip_path}")
                line = chip.get_line_by_offset(line_offset)
                _ = line.info  # validar acceso
                return chip
            except (OSError, AttributeError, RuntimeError):
                continue
    raise RuntimeError(f"No gpiochip found with line offset {line_offset}")

class TM1637:
    def __init__(self, clk, dio, brightness=7):
        self.clk = clk
        self.dio = dio

        if not 0 <= brightness <= 7:
            raise ValueError("Brightness out of range")
        self._brightness = brightness

        self.chip = find_gpiochip_for_line(self.clk)
        self.clk_line = self.chip.get_line_by_offset(self.clk)
        self.dio_line = self.chip.get_line_by_offset(self.dio)

        self.clk_line.request(consumer="tm1637", type=gpiod.Line.REQUEST_DIRECTION_OUTPUT, default_vals=[0])
        self.dio_line.request(consumer="tm1637", type=gpiod.Line.REQUEST_DIRECTION_OUTPUT, default_vals=[0])

    def _set_clk(self, value):
        self.clk_line.set_value(value)

    def _set_dio(self, value):
        self.dio_line.set_value(value)

    def _start(self):
        self._set_clk(1)
        self._set_dio(1)
        self._set_dio(0)
        self._set_clk(0)

    def _stop(self):
        self._set_clk(0)
        self._set_dio(0)
        self._set_clk(1)
        self._set_dio(1)

    def _write_data_cmd(self):
        self._start()
        self._write_byte(TM1637_CMD1)
        self._stop()

    def _write_dsp_ctrl(self):
        self._start()
        self._write_byte(TM1637_CMD3 | TM1637_DSP_ON | self._brightness)
        self._stop()

    def _write_byte(self, b):
        for i in range(8):
            self._set_dio((b >> i) & 1)
            sleep(TM1637_DELAY)
            self._set_clk(1)
            sleep(TM1637_DELAY)
            self._set_clk(0)
            sleep(TM1637_DELAY)

        self._set_clk(0)
        sleep(TM1637_DELAY)
        self._set_clk(1)
        sleep(TM1637_DELAY)
        self._set_clk(0)

    def brightness(self, val=None):
        if val is None:
            return self._brightness
        if not 0 <= val <= 7:
            raise ValueError("Brightness out of range")
        self._brightness = val
        self._write_data_cmd()
        self._write_dsp_ctrl()

    def write(self, segments, pos=0):
        if not 0 <= pos <= 3:
            raise ValueError("Position out of range")
        self._write_data_cmd()
        self._start()
        self._write_byte(TM1637_CMD2 | pos)
        for seg in segments:
            self._write_byte(seg)
        self._stop()
        self._write_dsp_ctrl()

    def encode_digit(self, digit):
        return _SEGMENTS[digit & 0x0F]

    def encode_string(self, string):
        segments = bytearray(len(string))
        for i, char in enumerate(string):
            segments[i] = self.encode_char(char)
        return segments

    def encode_char(self, char):
        o = ord(char)
        if o == 32:
            return _SEGMENTS[36]
        if o == 42:
            return _SEGMENTS[38]
        if o == 45:
            return _SEGMENTS[37]
        if 65 <= o <= 90:
            return _SEGMENTS[o - 55]
        if 97 <= o <= 122:
            return _SEGMENTS[o - 87]
        if 48 <= o <= 57:
            return _SEGMENTS[o - 48]
        raise ValueError(f"Character out of range: {o} '{char}'")

    def numbers(self, num1, num2, colon=True):
        num1 = max(-9, min(num1, 99))
        num2 = max(-9, min(num2, 99))
        segments = self.encode_string(f"{num1:02}{num2:02}")
        if colon:
            segments[1] |= 0x80
        self.write(segments)

    def temperature(self, num):
        if num < -9:
            self.show('lo')
        elif num > 99:
            self.show('hi')
        else:
            string = '{0: >2d}'.format(num)
            self.write(self.encode_string(string))
        self.write([_SEGMENTS[38], _SEGMENTS[12]], 2)

    def show(self, string, colon=False):
        segments = self.encode_string(string)
        if len(segments) > 1 and colon:
            segments[1] |= 128
        self.write(segments[:4])

    def scroll(self, string, delay=250):
        segments = self.encode_string(string)
        data = [0] * 8
        data[4:0] = list(segments)
        for i in range(len(segments) + 5):
            self.write(data[i: i + 4])
            sleep(delay / 1000)
