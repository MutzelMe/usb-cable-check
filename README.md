# USB-A ↔ C Cable Certification Tester

Test and certify your USB-A to USB-C cables for speed, stability, and quality.

---

## Features

- USB Version Detection: Identifies USB 2.0, 3.0, 3.1, and 3.2 standards.
- Power Delivery Check: Detects 500mA or 900mA power delivery.
- Stability Test: Monitors for USB errors and disconnections.
- Data Pin Check: Verifies D+/D- data pins for bulk/interrupt endpoints.
- Transfer Speed Test: Measures real-world transfer speed (Mbps).
- Cable Quality Estimation: Rates cable quality based on configurations.
- Perfect Table Alignment: Clean, color-coded terminal output.
- Detailed Logging: Saves all results to `usb_cable_test.log`.

---

## Requirements

- Linux (uses `lsusb`, `dmesg`, `gio`)
- Python 3.5+
- Optional: `colorama` for colored output (`pip install colorama`)

---

## Usage

1. Connect your USB-A ↔ C cable to your Linux machine.
2. Connect an Android device in MTP mode (File Transfer).
3. Run the script:
   ```bash
   chmod +x usb_cable_chk.py
   python3 ./usb_cable_chk.py
   ```
4. Follow the on-screen instructions.

---

## Output

- Terminal: Color-coded table with test results.
- Log File: Detailed results saved to `usb_cable_test.log`.

---

## Example Output

```
🏆 USB-A ↔  C CERTIFICATION TEST
┌──────────────────────┬──────────────────────┬──────────────┐
│ PARAMETER            │ RESULT               │ STATUS       │
├──────────────────────┼──────────────────────┼──────────────┤
│ USB Version          │ USB 3.2 Gen 2        │ ⭐⭐ (2/3)   │
│ Power Delivery       │ 900mA                │ ⭐⭐ (2/3)   │
│ Data Speed           │ 350Mbps (5/5)        │ ⭐⭐⭐ (3/3) │
│ Stability            │ 0 Errors             │ ✅           │
│ Data Pins (D+/D-)    │ OK                   │ ✅           │
│ Cable Quality        │ 2 Configs            │ ✅           │
└──────────────────────┴──────────────────────┴──────────────┘

📊 OVERALL: 5/6 TESTS PASSED (83%)
⭐ USB CERTIFIED
```

---

## Notes

- MTP Mode Required: Android device must be in File Transfer (MTP) mode.
- Root Not Required: Runs with standard user permissions.
- Tested on Ubuntu/Debian: May require adjustments for other distros.
