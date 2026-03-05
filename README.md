# USB-A ↔ C Cable Certification Tester

**Test and certify your USB-A to USB-C cables for speed, stability, and quality.**

---

## Features

- **USB Version Detection**: Identifies USB 2.0, 3.0, 3.1, and 3.2 standards.
- **Power Delivery Check**: Detects 500mA or 900mA power delivery.
- **Stability Test**: Monitors for USB errors and disconnections.
- **Data Pin Check**: Verifies D+/D- data pins for bulk/interrupt endpoints.
- **Transfer Speed Test**: Measures real-world transfer speed (Mbps).
- **Cable Quality Estimation**: Rates cable quality based on configurations.
- **Perfect Table Alignment**: Clean, color-coded terminal output.
- **Detailed Logging**: Saves all results to `usb_cable_test.log`.

---

## Requirements

- **Linux** (uses `lsusb`, `dmesg`, `gio`)
- **Python 3.5+**
- **Optional**: `colorama` for colored output (`pip install colorama`)

---

## Usage

1. **Connect your USB-A ↔ C cable** to your Linux machine.
2. **Connect an Android device** in MTP mode (File Transfer).
3. **Run the script**:
   ```bash
   chmod +x usb_cable_chk.py
   ./usb_cable_chk.py
