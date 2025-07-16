#!/usr/bin/env python3
"""
Setup script for the video streaming application
This script handles dependency installation with fallbacks for common issues
"""

import subprocess
import sys
import os

def run_command(command, description):
    """Run a command and handle errors gracefully"""
    print(f"\n{description}...")
    try:
        result = subprocess.run(command, shell=True, capture_output=True, text=True)
        if result.returncode == 0:
            print(f"✓ {description} - SUCCESS")
            return True
        else:
            print(f"✗ {description} - FAILED")
            print(f"Error: {result.stderr}")
            return False
    except Exception as e:
        print(f"✗ {description} - EXCEPTION: {e}")
        return False

def install_package(package, description=None):
    """Install a single package with error handling"""
    if description is None:
        description = f"Installing {package}"
    
    commands = [
        f"pip install {package}",
        f"pip install --no-build-isolation {package}",
        f"pip install --only-binary=all {package}",
        f"python -m pip install {package}",
    ]
    
    for command in commands:
        print(f"\nTrying: {command}")
        if run_command(command, description):
            return True
    
    return False

def main():
    print("Video Streaming Application Setup")
    print("=" * 40)
    
    # Check Python version
    python_version = sys.version_info
    print(f"Python version: {python_version.major}.{python_version.minor}.{python_version.micro}")
    
    if python_version >= (3, 12):
        print("⚠️  Warning: Python 3.12+ detected. Some packages may need special handling.")
    
    # Upgrade pip first
    print("\nUpgrading pip...")
    run_command("python -m pip install --upgrade pip", "Upgrading pip")
    
    # Try to install setuptools (needed for some packages)
    print("\nInstalling setuptools...")
    run_command("pip install setuptools", "Installing setuptools")
    
    # Install packages one by one with fallbacks
    packages = [
        ("numpy", "Installing NumPy (numerical computing)"),
        ("opencv-python", "Installing OpenCV (computer vision)"),
        ("matplotlib", "Installing Matplotlib (plotting)"),
        ("psutil", "Installing psutil (system monitoring)"),
    ]
    
    failed_packages = []
    
    for package, description in packages:
        print(f"\n{'-' * 50}")
        if not install_package(package, description):
            failed_packages.append(package)
            
            # Try alternative packages
            if package == "opencv-python":
                print("Trying alternative: opencv-python-headless")
                if not install_package("opencv-python-headless", "Installing OpenCV (headless)"):
                    print("❌ OpenCV installation failed completely")
            elif package == "matplotlib":
                print("Trying with specific backend")
                if not install_package("matplotlib --no-deps", "Installing Matplotlib (no deps)"):
                    print("❌ Matplotlib installation failed")
    
    print(f"\n{'=' * 50}")
    print("INSTALLATION SUMMARY")
    print(f"{'=' * 50}")
    
    if not failed_packages:
        print("✅ All packages installed successfully!")
        print("\nYou can now run:")
        print("  python test_setup.py    # Test the installation")
        print("  python server.py        # Start the server")
        print("  python client.py        # Start the client")
    else:
        print(f"❌ Failed to install: {', '.join(failed_packages)}")
        print("\nManual installation options:")
        
        for package in failed_packages:
            if package == "opencv-python":
                print(f"\nFor OpenCV:")
                print("  Option 1: pip install opencv-python-headless")
                print("  Option 2: conda install opencv")
                print("  Option 3: Download from https://pypi.org/project/opencv-python/")
            elif package == "matplotlib":
                print(f"\nFor Matplotlib:")
                print("  Option 1: pip install --no-build-isolation matplotlib")
                print("  Option 2: conda install matplotlib")
            elif package == "numpy":
                print(f"\nFor NumPy:")
                print("  Option 1: pip install --only-binary=all numpy")
                print("  Option 2: conda install numpy")
            else:
                print(f"\nFor {package}:")
                print(f"  Option 1: pip install --no-build-isolation {package}")
                print(f"  Option 2: conda install {package}")
    
    print(f"\nIf you continue to have issues:")
    print("1. Try using Anaconda/Miniconda:")
    print("   conda create -n videostream python=3.11")
    print("   conda activate videostream")
    print("   conda install opencv numpy matplotlib psutil")
    print("\n2. Or use pre-compiled wheels:")
    print("   pip install --only-binary=all -r requirements.txt")
    print("\n3. For Python 3.12+ users:")
    print("   Consider using Python 3.11 for better compatibility")

if __name__ == "__main__":
    main()
