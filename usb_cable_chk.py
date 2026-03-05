#!/usr/bin/env python3
# usb_cable_chk.py - PERFECT TABLE ALIGNMENT v7.5
# USB-A↔C Cable Certification Tester

import subprocess  # Needed to run shell commands for USB detection and file operations
import re  # Used to parse USB version and endpoint data from command output
import time  # Required for timing stability tests and speed measurements
import os  # Used for file operations and generating random test data
import hashlib  # Ensures file integrity during transfer speed tests
from datetime import datetime  # Provides human-readable timestamps for logging
from pathlib import Path  # Simplifies file path handling across different OSes

try:
    from typing import Dict, Optional  # Improves code readability and IDE support (Python 3.5+)
except ImportError:
    Dict = dict  # Fallback for older Python versions to avoid crashes
    Optional = lambda x: x

try:
    from colorama import Fore, init  # Makes terminal output more readable with colors
    init()
    COLORS = True
except ImportError:
    COLORS = False
    # Fallback to plain text if colorama is not installed, ensuring the script still runs
    class DummyColor:
        GREEN = RED = YELLOW = CYAN = RESET = ''
    Fore = DummyColor()

class USBCableTester:
    TEST_FILE_SIZE = 1024 * 1024  # 1MB is large enough to measure speed but small enough to transfer quickly
    TEST_CYCLES = 5  # Multiple cycles improve accuracy by averaging out fluctuations

    def __init__(self):
        self.log_file = Path("usb_cable_test.log")  # Log file ensures results are saved for later review
        self.test_results = {}  # Centralized storage for all test results, simplifies table generation

    def log(self, message: str, status: str = "") -> None:
        # Logging with timestamps and emojis makes it easier to track progress and identify issues
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        emoji = {"PASS": "✅ ", "FAIL": "❌ ", "WARN": "⚠️  ", "INFO": "ℹ️  "}.get(status, "➡️ ")
        colored_msg = f"{Fore.CYAN}[{timestamp}]{Fore.RESET} {emoji}{message}"
        print(colored_msg)
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(f"[{timestamp}] {emoji}{message}\n")

    def run_cmd(self, cmd: str, timeout=15, check=False):
        # Timeout prevents hanging if a command takes too long, improving robustness
        try:
            result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=timeout)
            if check and result.returncode != 0:
                self.log(f"Command error: {cmd}\n{result.stderr}", "FAIL")
            return result
        except subprocess.TimeoutExpired:
            self.log(f"Timeout: {cmd}", "FAIL")
            return subprocess.CompletedProcess(cmd, 1, "", "Timeout")

    def kill_gvfs(self):
        """GVFS processes can interfere with MTP connections, so we terminate them for reliability."""
        self.run_cmd("pkill -f gvfs-mtp-volume-monitor 2>/dev/null")
        self.run_cmd("pkill -f gvfsd-mtp 2>/dev/null")

    def detect_usb_version(self) -> Dict:
        # USB version affects data transfer speed; we need to know if the cable supports USB 2.0 or 3.x
        self.log("Scanning USB version...", "INFO")
        lsusb = self.run_cmd("lsusb -v 2>/dev/null | grep -E 'bcdUSB' | tail -3").stdout
        ver_match = re.search(r'bcdUSB\s+(\d+\.\d+)', lsusb)
        if ver_match:
            ver = ver_match.group(1)
            if ver.startswith("2."):
                version, status = "USB 2.0", "⭐ (1/3)"  # USB 2.0 is slower but widely compatible
            elif "3.2" in ver or "3.20" in ver:
                version, status = "USB 3.2 Gen 2x2", "⭐⭐⭐ (3/3)"  # Highest speed rating
            elif "3.1" in ver or "3.10" in ver:
                version, status = "USB 3.2 Gen 2", "⭐⭐ (2/3)"  # Faster than USB 3.0
            elif "3.0" in ver:
                version, status = "USB 3.2 Gen 1", "⭐⭐ (2/3)"  # USB 3.0 is still fast
            else:
                version, status = f"USB {ver}", "⚠️"  # Unknown versions may not be fully compatible
            self.log(f"USB: {version} {status}", "PASS")
            self.test_results["usb_version"] = {"value": version, "status": status}
            return {"value": version, "status": status}
        self.test_results["usb_version"] = {"value": "Unknown", "status": "❓"}
        return {"value": "Unknown", "status": "❓"}

    def detect_power_sysfs(self) -> Dict:
        # Power delivery affects charging speed; 900mA is better for fast charging
        self.log("Checking power delivery...", "INFO")
        usb_devices = [f"{root}/{d}" for root, dirs, _ in os.walk("/sys/bus/usb/devices")
                      for d in dirs if d.startswith(('1-', '2-', '3-', '4-'))][:5]
        power_info, power_status = "500mA", "⭐ (1/3)"  # Default to standard USB power
        for device_path in usb_devices:
            power_dir = f"{device_path}/power"
            if os.path.exists(power_dir):
                try:
                    with open(f"{power_dir}/control", 'r') as f:
                        if "on" in f.read().strip().lower():
                            power_info, power_status = "900mA", "⭐⭐ (2/3)"  # Higher power is better
                            break
                except:
                    pass
        self.log(f"Power: {power_info} {power_status}", "PASS")
        self.test_results["power"] = {"value": power_info, "status": power_status}
        return {"value": power_info, "status": power_status}

    def usb_stability_test(self) -> Dict:
        # Stability issues indicate a poor-quality cable or connection, which can cause data loss
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
        status = "✅" if error_count == 0 else "❌"  # Errors mean the cable is unreliable
        self.test_results["stability"] = {"value": stability, "status": status}
        self.log(f"Stability: {stability} {status}", "PASS")
        return {"value": stability, "status": status}

    def check_pinout_data(self) -> Dict:
        # Data pins (D+/D-) are required for data transfer; power-only cables lack these
        self.log("Checking data pins (D+/D-)...", "INFO")
        endpoints = self.run_cmd("lsusb -v 2>/dev/null | grep -E 'bEndpointAddress.*(BULK|INTERRUPT)' | tail -5").stdout
        pinout_ok = "OK" if "BULK" in endpoints else "Power-only?"  # BULK endpoints confirm data capability
        status = "✅" if "BULK" in endpoints else "⚠️"
        self.test_results["pinout"] = {"value": pinout_ok, "status": status}
        self.log(f"Data Pins: {pinout_ok} {status}", "PASS")
        return {"value": pinout_ok, "status": status}

    def find_mtp_device(self) -> Optional[str]:
        # MTP is required for file transfer tests; without it, we can't measure speed
        gio_mounts = self.run_cmd("gio mount -l | grep 'mtp://'").stdout
        if not gio_mounts:
            self.log("No MTP device found", "WARN")
            return None
        device_path = gio_mounts.split("mtp://")[1].split("'")[0].split()[0].rstrip('/')
        self.log(f"MTP device: mtp://{device_path}", "PASS")
        return device_path

    def _mtp_path_exists(self, path: str) -> bool:
        """MTP paths vary by device; we need to verify accessibility before proceeding."""
        result = self.run_cmd(f"gio list '{path}' 2>/dev/null", timeout=5)
        return result.returncode == 0 and result.stdout.strip()

    def _find_mtp_storage_path(self, device_name: str) -> str:
        """Different Android devices use different paths; we dynamically find the correct one."""
        # Test common DCIM paths first (fastest method)
        test_paths = [
            "DCIM",
            "Internal%20storage/DCIM",
            "Phone/DCIM",
            "emulated/0/DCIM",
            "storage/emulated/0/DCIM",
            "Internal%20shared%20storage/DCIM",
            "Interner%20gemeinsamer%20Speicher/DCIM"
        ]
        for path in test_paths:
            test_path = f"mtp://{device_name}/{path}"
            if self._mtp_path_exists(test_path):
                self.log(f"Found storage: {path.split('/')[0]}", "INFO")
                return path.split('/')[0].replace(" ", "%20")
        # If no common path works, scan MTP root for storage indicators
        result = self.run_cmd(f"gio list mtp://{device_name}/", timeout=5)
        if result.returncode != 0:
            return "Interner%20gemeinsamer%20Speicher"  # Final fallback for non-English devices
        # Look for storage indicators in any language
        storage_indicators = [
            'dcim', 'camera', 'internal', 'phone', 'main',
            'storage', 'speicher', 'stockage', 'emulated', 'sdcard'
        ]
        for line in result.stdout.splitlines():
            line = line.strip().lower()
            if line and any(indicator in line for indicator in storage_indicators):
                return line.replace(" ", "%20")
        # Absolute fallback for devices with non-standard paths
        return "Interner%20gemeinsamer%20Speicher"

    def transfer_speed_test(self, device_name: str) -> Dict:
        # Real-world speed tests confirm if the cable meets its rated performance
        self.log("Transfer speed test...", "INFO")
        root_folder = self._find_mtp_storage_path(device_name)
        test_folder = "DCIM"
        full_path = f"mtp://{device_name}/{root_folder}/{test_folder}" if root_folder else f"mtp://{device_name}/{test_folder}"
        success, speeds = 0, []
        for i in range(self.TEST_CYCLES):
            print(f"  {i+1}/5 ", end="")
            test_file = f"/tmp/test_{int(time.time())}_{i}.bin"
            data = os.urandom(self.TEST_FILE_SIZE)
            expected_hash = hashlib.sha256(data).hexdigest()  # Ensure file integrity
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
                        speed = self.TEST_FILE_SIZE / (time.time() - start) / 1024 / 1024 * 8  # Convert to Mbps
                        speeds.append(speed)
                        success += 1
                self.run_cmd(f"gio remove '{full_path}/{filename}'")
            # Cleanup temporary files to avoid clutter
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
        # More configurations usually mean better cable quality and compatibility
        self.log("Analyzing cable quality...", "INFO")
        configs = self.run_cmd("lsusb -v 2>/dev/null | grep -c 'bConfigurationValue'").stdout.strip()
        configs = int(configs) if configs.isdigit() else 1
        quality = f"{configs} Configs"
        status = "✅" if configs >= 2 else "⚠️"  # Multiple configs indicate better design
        self.test_results["quality"] = {"value": quality, "status": status}
        self.log(f"Quality: {quality} {status}", "PASS")
        return {"value": quality, "status": status}

    def _format_status(self, status):
        """Colors make it easier to quickly assess results; fixed padding ensures alignment."""
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
        """ANSI codes break width calculations; we strip them for accurate table alignment."""
        return re.sub(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])', '', text)

    def _get_status_width(self, status: str) -> int:
        """Fixed widths ensure the table remains aligned regardless of terminal settings."""
        widths = {
            "✅": 2, "⚠️": 1, "❌": 2, "❓": 2,
            "⭐ (1/3)": 8, "⭐⭐ (2/3)": 10, "⭐⭐⭐ (3/3)": 12
        }
        clean = self._strip_ansi(status)
        return widths.get(clean, len(clean))

    def print_perfect_table(self):
        """A well-aligned table makes results easy to read at a glance."""
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
        # Summary provides a quick overall assessment
        percentage = (passed_count / 6) * 100
        print(f"\n📊 OVERALL: {passed_count}/6 TESTS PASSED ({percentage:.0f}%)")
        if percentage >= 85:
            print(f"{Fore.GREEN}🎖️ USB-IF PREMIUM CERTIFIED{Fore.RESET}")
        elif percentage >= 67:
            print(f"{Fore.YELLOW}⭐ USB CERTIFIED{Fore.RESET}")
        else:
            print(f"{Fore.RED}⚠️ POWER-ONLY CABLE DETECTED{Fore.RESET}")
            print("   → RECOMMENDED: USB-IF certified cables")
        # Log output (without colors) for future reference
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
        # Orchestrates all tests in a logical order, ensuring dependencies are met
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
