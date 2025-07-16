#!/usr/bin/env python3
"""
Quick test script for FFmpeg streaming
"""

import os
import subprocess
import time
import threading

def test_server():
    """Test server startup"""
    print("🧪 Testing FFmpeg Server...")
    
    # Find a video file
    video_files = []
    for file in os.listdir('.'):
        if file.lower().endswith(('.mp4', '.avi', '.mkv', '.mov')):
            video_files.append(file)
    
    if not video_files:
        print("❌ No video files found in current directory")
        print("💡 Please add a video file (.mp4, .avi, .mkv, .mov) to test")
        return False
    
    video_file = video_files[0]
    print(f"🎬 Using video file: {video_file}")
    
    try:
        # Start server in background
        server_process = subprocess.Popen(
            ['python', 'server_ffmpeg.py', video_file],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True
        )
        
        print("⏳ Server starting... (waiting 3 seconds)")
        time.sleep(3)
        
        # Check if server is still running
        if server_process.poll() is None:
            print("✅ Server appears to be running")
            
            # Try to start client
            print("🧪 Testing FFmpeg Client...")
            client_process = subprocess.Popen(
                ['python', 'client_ffmpeg.py'],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            
            print("⏳ Client starting... (waiting 5 seconds)")
            time.sleep(5)
            
            if client_process.poll() is None:
                print("✅ Client appears to be running")
                print("🎥 If you see an FFplay window, the streaming is working!")
                print("📋 Press Ctrl+C to stop both server and client")
                
                try:
                    # Keep running until user stops
                    while True:
                        time.sleep(1)
                except KeyboardInterrupt:
                    print("\n🛑 Stopping test...")
            else:
                print("❌ Client failed to start")
                stdout, stderr = client_process.communicate()
                print(f"Client stdout: {stdout}")
                print(f"Client stderr: {stderr}")
            
            # Stop client
            client_process.terminate()
            
        else:
            print("❌ Server failed to start")
            stdout, stderr = server_process.communicate()
            print(f"Server stdout: {stdout}")
            print(f"Server stderr: {stderr}")
        
        # Stop server
        server_process.terminate()
        
    except Exception as e:
        print(f"❌ Test failed: {e}")
        return False
    
    return True

def main():
    print("🎬 FFmpeg Streaming Test")
    print("=" * 30)
    
    # Check FFmpeg installation
    try:
        result = subprocess.run(['ffmpeg', '-version'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print("✅ FFmpeg found")
        else:
            print("❌ FFmpeg not working")
            return
    except FileNotFoundError:
        print("❌ FFmpeg not found - please install FFmpeg first")
        return
    
    try:
        result = subprocess.run(['ffplay', '-version'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print("✅ FFplay found")
        else:
            print("❌ FFplay not working")
            return
    except FileNotFoundError:
        print("❌ FFplay not found - please install FFmpeg first")
        return
    
    # Run test
    print("\n🧪 Starting streaming test...")
    test_server()

if __name__ == "__main__":
    main()
