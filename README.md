# TM1637 Display Library for Raspberry Pi 5 (gpiod-based)

This is a **modified version** of the [`raspberrypi-tm1637`](https://github.com/depklyon/raspberrypi-tm1637) library, adapted to work on **Raspberry Pi 5** using the **`gpiod`** backend.

## 🚀 Why this version?

The Raspberry Pi 5 uses a new GPIO controller that is **not compatible with `RPi.GPIO`**, which the original TM1637 library depends on.

This version replaces `RPi.GPIO` with **`gpiod` (libgpiod)**, the officially supported GPIO access method in Raspberry Pi OS (Bookworm and newer).

## 📥 Installation

1. **Install required dependencies**:

   ```bash
   sudo apt update
   sudo apt install python3-libgpiod gpiod
   ```

2. **Install the library via pip**:

   ```bash
   pip install tm1637-rpi5-gpiod
   ```

   Or clone manually:

   ```bash
   git clone https://github.com/villeparamio/tm1637-rpi5-gpiod.git
   cd tm1637-rpi5-gpiod
   pip install .
   ```

## 🧪 Example usage

```python
import tm1637
from time import sleep

CLK = 24  # GPIO24 (physical pin 18)
DIO = 23  # GPIO23 (physical pin 16)

display = tm1637.TM1637(clk=CLK, dio=DIO)
display.brightness(7)

while True:
    display.show("TEST")
    sleep(2)
    display.numbers(12, 34)
    sleep(2)
```

> Make sure your user is in the `gpio` group to access `/dev/gpiochip*` without root.  
> If needed: `sudo usermod -aG gpio $USER && sudo reboot`

## 🛠 Features

- ✅ Raspberry Pi 5 compatible
- ✅ Uses `gpiod`, not `RPi.GPIO`
- ✅ Works with standard 4-digit TM1637 LED displays
- ✅ Supports numbers, text, brightness and temperature

## 🔄 Original sources

- [mcauser/micropython-tm1637](https://github.com/mcauser/micropython-tm1637)
- [depklyon/raspberrypi-tm1637](https://github.com/depklyon/raspberrypi-tm1637)

## 📜 License

This project is licensed under the **MIT License**.
