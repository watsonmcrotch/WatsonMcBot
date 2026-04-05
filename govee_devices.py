import requests
import json
from typing import List, Dict, Optional
from dataclasses import dataclass
import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

@dataclass
class GoveeDevice:
    """Represents a Govee device with its properties"""
    device: str
    model: str
    device_name: str
    controllable: bool
    retrievable: bool
    support_cmds: List[str]
    support_turn: str
    support_brightness: str
    support_color: str
    support_color_tem: str

class GoveeAPI:
    """Main class for interacting with Govee API"""
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize Govee API client
        
        Args:
            api_key: Your Govee API key. If None, will try to load from environment
        """
        self.api_key = api_key or os.getenv('GOVEE_API_KEY')
        if not self.api_key:
            raise ValueError("API key is required. Set GOVEE_API_KEY environment variable or pass it directly.")
        
        self.base_url = "https://developer-api.govee.com/v1"
        self.headers = {
            "Govee-API-Key": self.api_key,
            "Content-Type": "application/json"
        }
        
    def get_devices(self) -> List[GoveeDevice]:
        """
        Retrieve all devices associated with your account
        
        Returns:
            List of GoveeDevice objects
        """
        try:
            response = requests.get(
                f"{self.base_url}/devices",
                headers=self.headers,
                timeout=10
            )
            
            response.raise_for_status()
            data = response.json()
            
            devices = []
            for device_data in data.get('data', {}).get('devices', []):
                device = GoveeDevice(
                    device=device_data.get('device', ''),
                    model=device_data.get('model', ''),
                    device_name=device_data.get('deviceName', ''),
                    controllable=device_data.get('controllable', False),
                    retrievable=device_data.get('retrievable', False),
                    support_cmds=device_data.get('supportCmds', []),
                    support_turn=device_data.get('properties', {}).get('supportTurn', ''),
                    support_brightness=device_data.get('properties', {}).get('supportBrightness', ''),
                    support_color=device_data.get('properties', {}).get('supportColor', ''),
                    support_color_tem=device_data.get('properties', {}).get('supportColorTem', '')
                )
                devices.append(device)
            
            return devices
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching devices: {e}")
            return []
        except json.JSONDecodeError as e:
            print(f"Error parsing response: {e}")
            return []
    
    def get_device_state(self, device: str, model: str) -> Optional[Dict]:
        """
        Get current state of a specific device
        
        Args:
            device: Device MAC address
            model: Device model
            
        Returns:
            Device state dictionary or None if error
        """
        try:
            response = requests.get(
                f"{self.base_url}/devices/state",
                headers=self.headers,
                params={"device": device, "model": model},
                timeout=10
            )
            
            response.raise_for_status()
            return response.json()
            
        except requests.exceptions.RequestException as e:
            print(f"Error fetching device state: {e}")
            return None
    
    def control_device(self, device: str, model: str, cmd: Dict) -> bool:
        """
        Control a specific device
        
        Args:
            device: Device MAC address
            model: Device model  
            cmd: Command dictionary (e.g., {"name": "turn", "value": "on"})
            
        Returns:
            True if successful, False otherwise
        """
        try:
            payload = {
                "device": device,
                "model": model,
                "cmd": cmd
            }
            
            response = requests.put(
                f"{self.base_url}/devices/control",
                headers=self.headers,
                json=payload,
                timeout=10
            )
            
            response.raise_for_status()
            return True
            
        except requests.exceptions.RequestException as e:
            print(f"Error controlling device: {e}")
            return False

def main():
    """Example usage of the Govee API"""
    
    try:
        # Initialize API client
        govee = GoveeAPI()
        
        # Get all devices
        print("Fetching your Govee devices...")
        devices = govee.get_devices()
        
        if not devices:
            print("No devices found or error occurred.")
            return
        
        print(f"\nFound {len(devices)} device(s):")
        print("-" * 80)
        
        for i, device in enumerate(devices, 1):
            print(f"\n{i}. Device Name: {device.device_name}")
            print(f"   Device ID: {device.device}")
            print(f"   Model: {device.model}")
            print(f"   Controllable: {device.controllable}")
            print(f"   Retrievable: {device.retrievable}")
            print(f"   Supported Commands: {', '.join(device.support_cmds)}")
            print(f"   Supports Turn: {device.support_turn}")
            print(f"   Supports Brightness: {device.support_brightness}")
            print(f"   Supports Color: {device.support_color}")
            print(f"   Supports Color Temperature: {device.support_color_tem}")
            
            # Get device state if retrievable
            if device.retrievable:
                print("   Getting current state...")
                state = govee.get_device_state(device.device, device.model)
                if state:
                    properties = state.get('data', {}).get('properties', [])
                    for prop in properties:
                        print(f"   {prop.get('online', 'Unknown')}: {prop}")
        
        # Example: Turn on the first controllable device
        controllable_devices = [d for d in devices if d.controllable]
        if controllable_devices:
            first_device = controllable_devices[0]
            print(f"\nExample: Turning on '{first_device.device_name}'...")
            
            success = govee.control_device(
                first_device.device,
                first_device.model,
                {"name": "turn", "value": "on"}
            )
            
            if success:
                print("Device turned on successfully!")
            else:
                print("Failed to turn on device.")
                
    except Exception as e:
        print(f"An error occurred: {e}")

if __name__ == "__main__":
    main()