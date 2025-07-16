#!/usr/bin/env python3
"""
Test script for the video streaming application
This script helps verify that all dependencies are installed correctly
"""

import sys
import subprocess
import importlib

def test_import(module_name, package_name=None):
    """Test if a module can be imported"""
    try:
        importlib.import_module(module_name)
        print(f"✓ {module_name} - OK")
        return True
    except ImportError as e:
        print(f"✗ {module_name} - FAILED: {e}")
        if package_name:
            print(f"  Install with: pip install {package_name}")
        return False

def test_opencv_camera():
    """Test if OpenCV can access the camera"""
    try:
        import cv2
        cap = cv2.VideoCapture(0)
        if cap.isOpened():
            ret, frame = cap.read()
            cap.release()
            if ret:
                print("✓ Camera access - OK")
                return True
            else:
                print("✗ Camera access - Camera detected but cannot read frames")
                return False
        else:
            print("✗ Camera access - No camera detected")
            return False
    except Exception as e:
        print(f"✗ Camera access - Error: {e}")
        return False

def test_network_ports():
    """Test if required network ports are available"""
    import socket
    
    ports_to_test = [8888, 8889, 8890]
    all_available = True
    
    for port in ports_to_test:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.bind(('localhost', port))
            sock.close()
            print(f"✓ Port {port} - Available")
        except socket.error:
            print(f"✗ Port {port} - In use or blocked")
            all_available = False
    
    return all_available

def main():
    print("Video Streaming Application - Dependency Test")
    print("=" * 50)
    
    # Test Python version
    python_version = sys.version_info
    if python_version >= (3, 7):
        print(f"✓ Python {python_version.major}.{python_version.minor} - OK")
    else:
        print(f"✗ Python {python_version.major}.{python_version.minor} - Requires Python 3.7+")
        return False
    
    print("\nTesting required modules:")
    print("-" * 30)
    
    # Test required modules
    modules = [
        ('cv2', 'opencv-python'),
        ('numpy', 'numpy'),
        ('matplotlib', 'matplotlib'),
        ('psutil', 'psutil'),
        ('socket', None),  # Built-in
        ('threading', None),  # Built-in
        ('json', None),  # Built-in
        ('struct', None),  # Built-in
        ('time', None),  # Built-in
    ]
    
    all_modules_ok = True
    for module, package in modules:
        if not test_import(module, package):
            all_modules_ok = False
    
    print("\nTesting hardware access:")
    print("-" * 30)
    
    camera_ok = test_opencv_camera()
    
    print("\nTesting network configuration:")
    print("-" * 30)
    
    ports_ok = test_network_ports()
    
    print("\nSummary:")
    print("-" * 30)
    
    if all_modules_ok and camera_ok and ports_ok:
        print("✓ All tests passed! You're ready to run the video streaming application.")
        print("\nTo start the application:")
        print("1. Run the server: python server.py")
        print("2. Run the client: python client.py")
        
    else:
        print("✗ Some tests failed. Please fix the issues above before running the application.")
        
        if not all_modules_ok:
            print("\nTo install missing dependencies:")
            print("pip install -r requirements.txt")
        
        if not camera_ok:
            print("\nCamera issues:")
            print("- Make sure your camera is connected and not in use by other applications")
            print("- Try changing the camera index in server.py (0 to 1, 2, etc.)")
            print("- The application will use a test pattern if no camera is available")
        
        if not ports_ok:
            print("\nPort issues:")
            print("- Close applications that might be using ports 8888, 8889, or 8890")
            print("- You can modify the port numbers in both server.py and client.py")
    
    print("\nFor bandwidth limiting on Windows:")
    print("Run as Administrator: .\\bandwidth_limiter.ps1 -Action limit -LimitMbps 1")

if __name__ == "__main__":
    main()
