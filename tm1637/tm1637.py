"""TM1637 Library for Raspberry Pi 5 using gpiod (GPIO character device).

Modified by: villeparamio
Original Python port: https://github.com/depklyon/raspberrypi-tm1637
Based on MicroPython TM1637 driver: https://github.com/mcauser/micropython-tm1637

License: MIT

Compatibility:
- gpiod v1 (python3-libgpiod 1.x, python3-gpiod, etc.)
- gpiod v2 (binding oficial: LineSettings, Direction, Value, request_lines)
"""

from time import sleep
import gpiod
import os

try:
    # gpiod v2 (binding oficial): tiene submódulo gpiod.line y LineSettings
    from gpiod.line import Direction as _Direction, Value as _Value  # type: ignore[attr-defined]
    _HAS_GPIOD_V2 = hasattr(gpiod, "LineSettings")
except Exception:  # gpiod v1 (python3-libgpiod clásico o python3-gpiod)
    _Direction = None  # type: ignore[assignment]
    _Value = None       # type: ignore[assignment]
    _HAS_GPIOD_V2 = False

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

def find_gpiochip_for_line(line_offset: int) -> gpiod.Chip:
    """
    Busca el /dev/gpiochip* que tenga la línea `line_offset`.

    Devuelve un objeto gpiod.Chip (tanto en v1 como en v2).
    Lanza RuntimeError si no encuentra ninguno.
    """
    last_error: Exception | None = None

    for chip_name in sorted(os.listdir("/dev")):
        if not chip_name.startswith("gpiochip"):
            continue

        chip_path = f"/dev/{chip_name}"

        try:
            chip = gpiod.Chip(chip_path)

            if _HAS_GPIOD_V2:
                # API v2: si la línea no existe, esto levanta excepción
                chip.get_line_info(line_offset)
            else:
                # API v1: probamos varios métodos según la versión
                get_line = getattr(chip, "get_line", None)
                get_line_by_offset = getattr(chip, "get_line_by_offset", None)

                if get_line is not None:
                    line = get_line(line_offset)
                elif get_line_by_offset is not None:
                    line = get_line_by_offset(line_offset)
                else:
                    raise AttributeError(
                        "Chip object has neither get_line nor get_line_by_offset"
                    )

                # Forzamos acceso a algún atributo para validar
                _ = getattr(line, "info", None)

            # Si ha llegado hasta aquí, este chip sirve
            return chip

        except Exception as exc:  # noqa: BLE001
            last_error = exc
            try:
                chip.close()
            except Exception:  # noqa: BLE001
                pass
            continue

    raise RuntimeError(f"No gpiochip found with line offset {line_offset}") from last_error

class TM1637:
    def __init__(self, clk: int, dio: int, brightness: int = 7):
        self.clk = int(clk)
        self.dio = int(dio)

        if not 0 <= brightness <= 7:
            raise ValueError("Brightness out of range")

        self._brightness = brightness
        self._use_v2 = bool(_HAS_GPIOD_V2)

        # Chip válido para la línea clk (en Pi todo va en el mismo)
        self.chip = find_gpiochip_for_line(self.clk)

        if self._use_v2:
            # --- Backend gpiod v2 ------------------------------------------
            self._init_backend_v2()
        else:
            # --- Backend gpiod v1 ------------------------------------------
            self._init_backend_v1()

    def _init_backend_v1(self) -> None:

        get_line = getattr(self.chip, "get_line", None)
        get_line_by_offset = getattr(self.chip, "get_line_by_offset", None)

        if get_line is not None:
            self.clk_line = get_line(self.clk)
            self.dio_line = get_line(self.dio)
        elif get_line_by_offset is not None:
            self.clk_line = get_line_by_offset(self.clk)
            self.dio_line = get_line_by_offset(self.dio)
        else:
            raise RuntimeError(
                "gpiod v1: Chip has no get_line or get_line_by_offset method"
            )

        req_type = None

        if hasattr(gpiod, "Line") and hasattr(gpiod.Line, "REQUEST_DIRECTION_OUTPUT"):
            req_type = gpiod.Line.REQUEST_DIRECTION_OUTPUT  # type: ignore[attr-defined]

        if req_type is None and hasattr(gpiod, "LINE_REQ_DIR_OUT"):
            req_type = gpiod.LINE_REQ_DIR_OUT  # type: ignore[attr-defined]

        if req_type is None:
            raise RuntimeError(
                "gpiod v1: cannot determine output request type "
                "(expected Line.REQUEST_DIRECTION_OUTPUT or LINE_REQ_DIR_OUT)"
            )

        self.clk_line.request(
            consumer="tm1637",
            type=req_type,
            default_vals=[0],
        )
        self.dio_line.request(
            consumer="tm1637",
            type=req_type,
            default_vals=[0],
        )

    def _init_backend_v2(self) -> None:

        if _Direction is None or _Value is None or not hasattr(gpiod, "LineSettings"):
            raise RuntimeError("gpiod v2 detected but LineSettings/Direction/Value missing")

        chip_path = getattr(self.chip, "path", None)
        if not chip_path:
            chip_path = "/dev/gpiochip0"

        settings = gpiod.LineSettings(  # type: ignore[attr-defined]
            direction=_Direction.OUTPUT,
            output_value=_Value.INACTIVE,
        )

        config = {
            self.clk: settings,
            self.dio: settings,
        }

        request_lines_fn = getattr(gpiod, "request_lines", None)
        if request_lines_fn is not None:
            self._request = request_lines_fn(
                chip_path,
                consumer="tm1637",
                config=config,
            )
        else:
            chip_request_lines = getattr(self.chip, "request_lines", None)
            if chip_request_lines is None:
                raise RuntimeError("gpiod v2: request_lines API not found")
            self._request = chip_request_lines(config, consumer="tm1637")

    def _set_clk(self, value: int) -> None:
        if self._use_v2:
            # API v2: set_value(offset, Value.ACTIVE/INACTIVE)
            self._request.set_value(
                self.clk,
                _Value.ACTIVE if value else _Value.INACTIVE,  # type: ignore[arg-type]
            )
        else:
            # API v1: line.set_value(0/1)
            self.clk_line.set_value(int(bool(value)))

    def _set_dio(self, value: int) -> None:
        if self._use_v2:
            self._request.set_value(
                self.dio,
                _Value.ACTIVE if value else _Value.INACTIVE,  # type: ignore[arg-type]
            )
        else:
            self.dio_line.set_value(int(bool(value)))

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

    def brightness(self, val: int | None = None) -> int | None:
        if val is None:
            return self._brightness

        if not 0 <= val <= 7:
            raise ValueError("Brightness out of range")

        self._brightness = val
        self._write_data_cmd()
        self._write_dsp_ctrl()
        return None

    def write(self, segments, pos: int = 0) -> None:
        if not 0 <= pos <= 3:
            raise ValueError("Position out of range")

        self._write_data_cmd()
        self._start()
        self._write_byte(TM1637_CMD2 | pos)

        for seg in segments:
            self._write_byte(seg)

        self._stop()
        self._write_dsp_ctrl()

    def encode_digit(self, digit: int) -> int:
        return _SEGMENTS[digit & 0x0F]

    def encode_string(self, string: str) -> bytearray:
        segments = bytearray(len(string))
        for i, char in enumerate(string):
            segments[i] = self.encode_char(char)
        return segments

    def encode_char(self, char: str) -> int:
        o = ord(char)

        if o == 32:  # espacio
            return _SEGMENTS[36]
        if o == 42:  # '*'
            return _SEGMENTS[38]
        if o == 45:  # '-'
            return _SEGMENTS[37]
        if 65 <= o <= 90:  # A-Z
            return _SEGMENTS[o - 55]
        if 97 <= o <= 122:  # a-z
            return _SEGMENTS[o - 87]
        if 48 <= o <= 57:  # 0-9
            return _SEGMENTS[o - 48]

        raise ValueError(f"Character out of range: {o} '{char}'")

    def numbers(self, num1: int, num2: int, colon: bool = True) -> None:
        num1 = max(-9, min(num1, 99))
        num2 = max(-9, min(num2, 99))

        segments = self.encode_string(f"{num1:02d}{num2:02d}")
        if colon:
            segments[1] |= TM1637_MSB  # activar dos puntos

        self.write(segments)

    def temperature(self, num: int) -> None:
        if num < -9:
            self.show("lo")
        elif num > 99:
            self.show("hi")
        else:
            string = "{0: >2d}".format(num)
            self.write(self.encode_string(string))
            self.write([_SEGMENTS[38], _SEGMENTS[12]], 2)  # °C

    def show(self, string: str, colon: bool = False) -> None:
        segments = self.encode_string(string)
        if len(segments) > 1 and colon:
            segments[1] |= TM1637_MSB
        self.write(segments[:4])


    def scroll(self, string: str, delay: int = 250) -> None:
        segments = self.encode_string(string)
        data = [0] * 8
        data[4:0] = list(segments)
        for i in range(len(segments) + 5):
            self.write(data[i : i + 4])
            sleep(delay / 1000.0)
