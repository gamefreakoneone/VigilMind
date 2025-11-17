import win32gui
import win32process
import psutil
import time
import requests
import base64
from io import BytesIO
from PIL import ImageGrab
import os
import sys

API_URL = "http://localhost:5000"
SCREENSHOT_INTERVAL = 120  # seconds (configurable via API)

class DesktopMonitor:
    def __init__(self):
        self.last_window = ""
        self.browser_processes = ['chrome.exe', 'firefox.exe', 'msedge.exe', 'brave.exe']
        self.running = True
        
    def get_active_window(self):
        try:
            hwnd = win32gui.GetForegroundWindow()
            window_title = win32gui.GetWindowText(hwnd)
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            process = psutil.Process(pid)
            process_name = process.name()
            
            return {
                'process_name': process_name,
                'window_title': window_title,
                'pid': pid
            }
        except Exception as e:
            print(f"Error getting window: {e}")
            return None
    
    def is_browser(self, process_name):
        return process_name.lower() in self.browser_processes
    
    def take_screenshot(self): #TODO: Save the screenshot for debugging
        try:
            screenshot = ImageGrab.grab()
            buffered = BytesIO()
            screenshot.save(buffered, format="PNG")
            img_str = base64.b64encode(buffered.getvalue()).decode()
            return img_str
        except Exception as e:
            print(f"Error taking screenshot: {e}")
            return None
    
    def send_to_api(self, window_info, screenshot_base64):
        try:
            response = requests.post(
                f"{API_URL}/desktop/screenshot", # This is missing. #TODO: Add this endpoint to the Flask server
                json={
                    'app_name': window_info['process_name'],
                    'window_title': window_info['window_title'],
                    'screenshot': screenshot_base64,
                    'pid': window_info['pid']
                },
                timeout=10
            )
            
            data = response.json()
            return data
            
        except Exception as e:
            print(f"Error sending to API: {e}")
            return None
    
    def terminate_app(self, pid):
        try:
            process = psutil.Process(pid)
            process.terminate()
            print(f"Terminated process {pid}")
            return True
        except Exception as e:
            print(f" Error terminating process: {e}")
            return False
    
    def get_config_from_api(self):
        """Fetch monitoring configuration from API"""
        try:
            response = requests.get(f"{API_URL}/config", timeout=5)
            return response.json()
        except:
            return {
                'desktop_monitoring_enabled': True,
                'screenshot_interval': 120
            }
    
    def monitor(self):
        """Main monitoring loop"""
        print("Desktop Monitor Started")
        print("=" * 50)
        
        last_screenshot_time = 0
        
        while self.running:
            try:
                # Get config periodically
                config = self.get_config_from_api()
                
                if not config.get('desktop_monitoring_enabled', True):
                    print("Desktop monitoring disabled, waiting...")
                    time.sleep(10)
                    continue
                
                # Get active window
                window_info = self.get_active_window()
                
                if not window_info:
                    time.sleep(2)
                    continue
                
                process_name = window_info['process_name']
                window_title = window_info['window_title']
                
                # Log window changes
                current_window = f"{process_name}: {window_title}"
                if current_window != self.last_window:
                    print(f"\n[{time.strftime('%H:%M:%S')}] Active: {current_window}")
                    self.last_window = current_window
                
                # Skip browsers (already monitored by extension)
                if self.is_browser(process_name):
                    time.sleep(2)
                    continue
                
                # Take screenshot at intervals
                current_time = time.time()
                screenshot_interval = config.get('screenshot_interval', SCREENSHOT_INTERVAL)
                
                if current_time - last_screenshot_time >= screenshot_interval:
                    print(f" Taking screenshot of {process_name}...")
                    
                    screenshot_base64 = self.take_screenshot()
                    
                    if screenshot_base64:
                        # Send to API
                        result = self.send_to_api(window_info, screenshot_base64)
                        
                        if result:
                            if result.get('action') == 'terminate':
                                print(f" Terminating {process_name}: {result.get('reason')}")
                                self.terminate_app(window_info['pid'])
                            elif result.get('action') == 'allow':
                                print(f" {process_name} - Activity allowed")
                    
                    last_screenshot_time = current_time
                
                time.sleep(2)  # Check window changes frequently
                
            except KeyboardInterrupt:
                print("\n\n  Monitoring stopped by user")
                self.running = False
                break
            except Exception as e:
                print(f" Error in monitoring loop: {e}")
                time.sleep(5)
    
    def start(self):
        """Start monitoring"""
        print("\n" + "="*50)
        print("PARENTAL DESKTOP MONITOR")
        print("="*50)
        print("This will monitor all non-browser applications")
        print("Press Ctrl+C to stop")
        print("="*50 + "\n")
        
        # Check if API is reachable
        try:
            requests.get(f"{API_URL}/health", timeout=5)
            print(" Connected to monitoring service\n")
        except:
            print("  Warning: Cannot connect to monitoring service")
            print("   Make sure the Flask server is running on port 5000\n")
        
        self.monitor()


def main():
    # Check if running with admin privileges (needed for some operations)
    try:
        is_admin = os.getuid() == 0
    except AttributeError:
        import ctypes
        is_admin = ctypes.windll.shell32.IsUserAnAdmin() != 0
    
    if not is_admin:
        print("  Warning: Not running as administrator")
        print("   Some features may not work properly")
        print("   Consider running as administrator\n")
    
    monitor = DesktopMonitor()
    monitor.start()


if __name__ == "__main__":
    main()