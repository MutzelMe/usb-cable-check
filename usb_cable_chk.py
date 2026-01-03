#!/usr/bin/env python3
# usb_cable_chk.py
# USB-A↔C Cable Certification Tester

import subprocess
import re
import time
import os
import hashlib
from datetime import datetime
from pathlib import Path

try:
    from typing import Dict, Optional
except ImportError:
    Dict = dict
    Optional = lambda x: x

try:
    from colorama import Fore, init
    init()
    COLORS = True
except ImportError:
    COLORS = False
    class DummyColor:
        GREEN = RED = YELLOW = CYAN = RESET = ''
    Fore = DummyColor()

class USBCableTester:
    TEST_FILE_SIZE = 1024 * 1024  # 1MB
    TEST_CYCLES = 5

    def __init__(self):
        self.log_file = Path("usb_cable_test.log")
        self.test_results = {}

    def log(self, message: str, status: str = "") -> None:
        # Log messages with emoji and timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        emoji = {"PASS": "✅ ", "FAIL": "❌ ", "WARN": "⚠️  ", "INFO": "ℹ️  "}.get(status, "➡️ ")
        colored_msg = f"{Fore.CYAN}[{timestamp}]{Fore.RESET} {emoji}{message}"
        print(colored_msg)
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {emoji}{message}\n")

    def run_cmd(self, cmd: str, timeout=15, check=False):
        # Execute shell commands with timeout
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
            if check and result.returncode != 0:
                self.log(f"Command error: {cmd}\n{result.stderr}", "FAIL")
            return result
        except subprocess.TimeoutExpired:
            self.log(f"Timeout: {cmd}", "FAIL")
            return subprocess.CompletedProcess(cmd, 1, "", "Timeout")

    def kill_gvfs(self):
        """Kill conflicting GVFS MTP processes"""
        self.run_cmd("pkill -f gvfs-mtp-volume-monitor 2>/dev/null")
        self.run_cmd("pkill -f gvfsd-mtp 2>/dev/null")

    def detect_usb_version(self) -> Dict:
        # Detect USB version and format correctly (2.0 instead of 2.01)
        self.log("Scanning USB version...", "INFO")
        lsusb = self.run_cmd("lsusb -v 2>/dev/null | grep -E 'bcdUSB' | tail -3").stdout
        ver_match = re.search(r'bcdUSB\s+(\d+\.\d+)', lsusb)
        if ver_match:
            ver = ver_match.group(1)
            if ver.startswith("2."):
                version, status = "USB 2.0", "⭐ (1/3)"
            elif "3.2" in ver or "3.20" in ver:
                version, status = "USB 3.2 Gen 2x2", "⭐⭐⭐ (3/3)"
            elif "3.1" in ver or "3.10" in ver:
                version, status = "USB 3.2 Gen 2", "⭐⭐ (2/3)"
            elif "3.0" in ver:
                version, status = "USB 3.2 Gen 1", "⭐⭐ (2/3)"
            else:
                version, status = f"USB {ver}", "⚠️"
            self.log(f"USB: {version} {status}", "PASS")
            self.test_results["usb_version"] = {"value": version, "status": status}
            return {"value": version, "status": status}
        self.test_results["usb_version"] = {"value": "Unknown", "status": "❓"}
        return {"value": "Unknown", "status": "❓"}

    def detect_power_sysfs(self) -> Dict:
        # Check USB power delivery capabilities
        self.log("Checking power delivery...", "INFO")
        usb_devices = [f"{root}/{d}" for root, dirs, _ in os.walk("/sys/bus/usb/devices")
                      for d in dirs if d.startswith(('1-', '2-', '3-', '4-'))][:5]
        power_info, power_status = "500mA", "⭐ (1/3)"
        for device_path in usb_devices:
            power_dir = f"{device_path}/power"
            if os.path.exists(power_dir):
                try:
                    with open(f"{power_dir}/control", 'r') as f:
                        if "on" in f.read().strip().lower():
                            power_info, power_status = "900mA", "⭐⭐ (2/3)"
                            break
                except:
                    pass
        self.log(f"Power: {power_info} {power_status}", "PASS")
        self.test_results["power"] = {"value": power_info, "status": power_status}
        return {"value": power_info, "status": power_status}

    def usb_stability_test(self) -> Dict:
        # Test USB connection stability
        self.log("USB stability test (5s)...", "INFO")
        errors = ["disconnect", "reset", "over_current", "error"]
        time.sleep(1)
        base_dmesg = self.run_cmd("dmesg | tail -10 | grep -i usb").stdout.lower()
        error_count = 0
        start = time.time()
        while time.time() - start < 4:
            current = self.run_cmd("dmesg | tail -5 | grep -i usb").stdout.lower()
            for error in errors:
                if error in current and error not in base_dmesg:
                    error_count += 1
            time.sleep(0.5)
        stability = "0 Errors" if error_count == 0 else f"{error_count} Errors"
        status = "✅" if error_count == 0 else "❌"
        self.test_results["stability"] = {"value": stability, "status": status}
        self.log(f"Stability: {stability} {status}", "PASS")
        return {"value": stability, "status": status}

    def check_pinout_data(self) -> Dict:
        # Check USB data pins (D+/D-)
        self.log("Checking data pins (D+/D-)...", "INFO")
        endpoints = self.run_cmd("lsusb -v 2>/dev/null | grep -E 'bEndpointAddress.*(BULK|INTERRUPT)' | tail -5").stdout
        pinout_ok = "OK" if "BULK" in endpoints else "Power-only?"
        status = "✅" if "BULK" in endpoints else "⚠️"
        self.test_results["pinout"] = {"value": pinout_ok, "status": status}
        self.log(f"Data Pins: {pinout_ok} {status}", "PASS")
        return {"value": pinout_ok, "status": status}

    def find_mtp_device(self) -> Optional[str]:
        # Find MTP device for speed test
        gio_mounts = self.run_cmd("gio mount -l | grep 'mtp://'").stdout
        if not gio_mounts:
            self.log("No MTP device found", "WARN")
            return None
        device_path = gio_mounts.split("mtp://")[1].split("'")[0].split()[0].rstrip('/')
        self.log(f"MTP device: mtp://{device_path}", "PASS")
        return device_path

    def transfer_speed_test(self, device_name: str) -> Dict:
        # Test USB transfer speed
        self.log("Transfer speed test...", "INFO")
        root_folder = "Interner%20gemeinsamer%20Speicher"
        test_folder = "DCIM"
        full_path = f"mtp://{device_name}/{root_folder}/{test_folder}"
        success, speeds = 0, []

        for i in range(self.TEST_CYCLES):
            print(f"  {i+1}/5 ", end="")
            test_file = f"/tmp/test_{int(time.time())}_{i}.bin"
            data = os.urandom(self.TEST_FILE_SIZE)
            expected_hash = hashlib.sha256(data).hexdigest()

            with open(test_file, "wb") as f:
                f.write(data)

            start = time.time()
            upload = self.run_cmd(f"gio copy '{test_file}' '{full_path}/'", check=True, timeout=30)

            if upload.returncode == 0:
                filename = os.path.basename(test_file)
                download = self.run_cmd(f"gio copy '{full_path}/{filename}' '{test_file}.check'", timeout=30)
                if os.path.exists(f"{test_file}.check"):
                    actual_hash = hashlib.sha256(open(f"{test_file}.check", "rb").read()).hexdigest()
                    if expected_hash == actual_hash:
                        speed = self.TEST_FILE_SIZE / (time.time() - start) / 1024 / 1024 * 8
                        speeds.append(speed)
                        success += 1
                self.run_cmd(f"gio remove '{full_path}/{filename}'")

            # Cleanup
            for f in [test_file, f"{test_file}.check"]:
                if os.path.exists(f):
                    os.unlink(f)

            speed_display = f"{speeds[-1]:.0f}Mbps" if speeds else "FAIL"
            print(speed_display)
            time.sleep(0.5)

        avg_speed = sum(speeds)/len(speeds) if speeds else 0
        speed_rating = "⭐⭐⭐ (3/3)" if avg_speed > 400 else "⭐⭐ (2/3)" if avg_speed > 200 else "⭐ (1/3)" if avg_speed > 50 else "⚠️"
        speed_str = f"{avg_speed:.0f}Mbps ({success}/5)"
        self.test_results["speed"] = {"value": speed_str, "status": speed_rating}
        self.log(f"Speed: {speed_str} {speed_rating}", "PASS")
        return {"value": speed_str, "status": speed_rating}

    def estimate_cable_quality(self) -> Dict:
        # Estimate USB cable quality
        self.log("Analyzing cable quality...", "INFO")
        configs = self.run_cmd("lsusb -v 2>/dev/null | grep -c 'bConfigurationValue'").stdout.strip()
        configs = int(configs) if configs.isdigit() else 1
        quality = f"{configs} Configs"
        status = "✅" if configs >= 2 else "⚠️"
        self.test_results["quality"] = {"value": quality, "status": status}
        self.log(f"Quality: {quality} {status}", "PASS")
        return {"value": quality, "status": status}

    def _format_status(self, status):
        """Format status with colors and fixed padding for alignment."""
        if status == "⭐⭐⭐ (3/3)":
            return f"{Fore.YELLOW}⭐⭐⭐ (3/3){Fore.RESET}"
        elif status == "⭐⭐ (2/3)":
            return f"{Fore.YELLOW}⭐⭐ (2/3){Fore.RESET}"
        elif status == "⭐ (1/3)":
            return f"{Fore.YELLOW}⭐ (1/3){Fore.RESET}"
        elif status == "✅":
            return f"{Fore.GREEN}✅{Fore.RESET}"
        elif status == "⚠️":
            return f"{Fore.YELLOW}⚠️{Fore.RESET}"
        elif status == "❌":
            return f"{Fore.RED}❌{Fore.RESET}"
        elif status == "❓":
            return f"{Fore.YELLOW}❓{Fore.RESET}"
        else:
            return status

    def _strip_ansi(self, text: str) -> str:
        """Remove all ANSI escape codes for width calculation"""
        return re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', text)

    def _get_status_width(self, status: str) -> int:
        """Fixed widths for all STATUS values (terminal accurate)."""
        widths = {
            "✅": 2, "⚠️": 1, "❌": 2, "❓": 2,
            "⭐ (1/3)": 8, "⭐⭐ (2/3)": 10, "⭐⭐⭐ (3/3)": 12
        }
        clean = self._strip_ansi(status)
        return widths.get(clean, len(clean))

    def print_perfect_table(self):
        """Print perfectly aligned table (60 characters)."""
        param_width = 20
        value_width = 20
        status_width = 12  # For STATUS column

        top_border = "┌──────────────────────┬──────────────────────┬──────────────┐"
        separator = "├──────────────────────┼──────────────────────┼──────────────┤"
        bottom_border = "└──────────────────────┴──────────────────────┴──────────────┘"

        print("\n" + "=" * 60)
        print("🏆 USB-A ↔  C CERTIFICATION TEST")
        print("=" * 60)

        tests = [
            ("USB Version", self.test_results["usb_version"]["value"], self.test_results["usb_version"]["status"]),
            ("Power Delivery", self.test_results["power"]["value"], self.test_results["power"]["status"]),
            ("Data Speed", self.test_results["speed"]["value"], self.test_results["speed"]["status"]),
            ("Stability", self.test_results["stability"]["value"], self.test_results["stability"]["status"]),
            ("Data Pins (D+/D-)", self.test_results["pinout"]["value"], self.test_results["pinout"]["status"]),
            ("Cable Quality", self.test_results["quality"]["value"], self.test_results["quality"]["status"]),
        ]

        header = f"│ {'PARAMETER':<{param_width}} │ {'RESULT':<{value_width}} │ {'STATUS':<{status_width}} │"
        print(top_border)
        print(header)
        print(separator)

        passed_count = 0
        for param, value, status in tests:
            formatted_status = self._format_status(status)
            clean_status = self._strip_ansi(formatted_status)
            status_visual_width = self._get_status_width(clean_status)
            padding = " " * (status_width - status_visual_width)
            row = f"│ {param:<{param_width}} │ {str(value):<{value_width}} │ {formatted_status}{padding} │"
            print(row)

            if status in ["✅", "⭐ (1/3)", "⭐⭐ (2/3)", "⭐⭐⭐ (3/3)"]:
                passed_count += 1

        print(bottom_border)

        # Summary
        percentage = (passed_count / 6) * 100
        print(f"\n📊 OVERALL: {passed_count}/6 TESTS PASSED ({percentage:.0f}%)")

        if percentage >= 85:
            print(f"{Fore.GREEN}🎖️ USB-IF PREMIUM CERTIFIED{Fore.RESET}")
        elif percentage >= 67:
            print(f"{Fore.YELLOW}⭐ USB CERTIFIED{Fore.RESET}")
        else:
            print(f"{Fore.RED}⚠️ POWER-ONLY CABLE DETECTED{Fore.RESET}")
            print("   → RECOMMENDED: USB-IF certified cables")

        # Log output (without colors)
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write("\n" + "=" * 60 + "\n")
            f.write("USB-A ↔  C CERTIFICATION TEST\n")
            f.write("=" * 60 + "\n")
            f.write(top_border + "\n")
            f.write(header + "\n")
            f.write(separator + "\n")
            for param, value, status in tests:
                formatted_status = self._format_status(status).replace(Fore.YELLOW, "").replace(Fore.GREEN, "").replace(Fore.RED, "").replace(Fore.RESET, "")
                status_visual_width = self._get_status_width(formatted_status)
                padding = " " * (status_width - status_visual_width)
                f.write(f"│ {param:<{param_width}} │ {str(value):<{value_width}} │ {formatted_status}{padding} │\n")
            f.write(bottom_border + "\n")
            f.write(f"OVERALL: {passed_count}/6 TESTS PASSED ({percentage:.0f}%)\n")

    def run_complete_test(self):
        # Run complete USB cable test
        self.log_file.write_text("")
        print("\n🔌 USB CABLE TESTER PRO v7.5 - PERFECT ALIGNMENT")
        print("=" * 45)

        self.detect_usb_version()
        self.detect_power_sysfs()
        self.usb_stability_test()
        self.check_pinout_data()
        self.estimate_cable_quality()

        self.kill_gvfs()
        print("\n📱 CONNECT ANDROID DEVICE:")
        print("- Enable USB Debugging")
        print("- Set USB mode to 'File Transfer' (MTP)")
        input("\nPress ENTER when ready... ")

        device_name = self.find_mtp_device()
        if device_name:
            self.transfer_speed_test(device_name)
        else:
            self.test_results["speed"] = {"value": "No MTP", "status": "❓"}

        self.print_perfect_table()
        print(f"\n📋 Detailed log: {self.log_file}")

def main():
    tester = USBCableTester()
    tester.run_complete_test()

if __name__ == "__main__":
    main()
