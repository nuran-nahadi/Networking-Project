#!/usr/bin/env python3
"""
Video Streaming Application Launcher
Easy way to start server with a video file and client
"""

import os
import sys
import subprocess
import time
import threading

def find_video_files(directory="."):
    """Find video files in the current directory"""
    video_extensions = ['.mp4', '.avi', '.mov', '.mkv', '.wmv', '.flv', '.webm']
    video_files = []
    
    for file in os.listdir(directory):
        if any(file.lower().endswith(ext) for ext in video_extensions):
            video_files.append(file)
    
    return sorted(video_files)

def show_menu():
    """Show the main menu"""
    print("🎥 Video Streaming Application Launcher")
    print("=" * 50)
    print()
    
    # Find video files in current directory
    video_files = find_video_files()
    
    if video_files:
        print("📁 Found video files in current directory:")
        for i, video in enumerate(video_files, 1):
            print(f"  {i}. {video}")
        print()
    
    print("Choose an option:")
    print("1. 📁 Browse for video file")
    print("2. 🧪 Use animated test pattern")
    if video_files:
        print("3. 📋 Select from found videos")
    print("4. ❓ Help")
    print("0. 🚪 Exit")
    print()

def browse_file():
    """Browse for a video file"""
    try:
        import tkinter as tk
        from tkinter import filedialog
        
        root = tk.Tk()
        root.withdraw()  # Hide the main window
        
        file_path = filedialog.askopenfilename(
            title="Select Video File",
            filetypes=[
                ("Video files", "*.mp4 *.avi *.mov *.mkv *.wmv *.flv *.webm"),
                ("MP4 files", "*.mp4"),
                ("All files", "*.*")
            ]
        )
        
        root.destroy()
        return file_path if file_path else None
        
    except ImportError:
        print("Tkinter not available. Please enter the full path manually:")
        return input("Video file path: ").strip().strip('"')

def start_server(video_path=None):
    """Start the server in a new process"""
    if video_path:
        cmd = [sys.executable, "server.py", video_path]
        print(f"🚀 Starting server with video: {os.path.basename(video_path)}")
    else:
        cmd = [sys.executable, "server.py"]
        print("🚀 Starting server with webcam/test pattern")
    
    return subprocess.Popen(cmd)

def start_client():
    """Start the client in a new process"""
    print("🚀 Starting client...")
    return subprocess.Popen([sys.executable, "client.py"])

def show_help():
    """Show help information"""
    print()
    print("📚 Video Streaming Application Help")
    print("=" * 40)
    print()
    print("This application demonstrates adaptive video streaming with")
    print("dynamic resolution switching based on network conditions.")
    print()
    print("🎯 Features:")
    print("  • Video file streaming (MP4, AVI, MOV, etc.)")
    print("  • Multi-resolution streaming (low/medium/high)")
    print("  • Real-time network monitoring")
    print("  • Adaptive resolution switching")
    print("  • Live performance visualization")
    print("  • Animated test pattern (when no video file)")
    print()
    print("🎮 Controls (in video window):")
    print("  • 'q' - Quit application")
    print("  • 'f' - Toggle fullscreen")
    print("  • 'w' - Return to windowed mode")
    print()
    print("🔧 Testing bandwidth adaptation:")
    print("  1. Run: .\\bandwidth_limiter.ps1 -Action limit -LimitMbps 1")
    print("  2. Start this application")
    print("  3. Watch resolution adapt to limited bandwidth")
    print("  4. Run: .\\bandwidth_limiter.ps1 -Action remove")
    print()
    print("📂 Supported video formats:")
    print("  MP4, AVI, MOV, MKV, WMV, FLV, WebM")
    print()

def main():
    """Main launcher function"""
    while True:
        show_menu()
        
        try:
            choice = input("Enter your choice (0-4): ").strip()
            
            if choice == "0":
                print("👋 Goodbye!")
                break
                
            elif choice == "1":
                # Browse for file
                video_path = browse_file()
                if video_path and os.path.exists(video_path):
                    print(f"\n✅ Selected: {video_path}")
                    input("Press Enter to start server and client...")
                    
                    server_process = start_server(video_path)
                    time.sleep(2)  # Give server time to start
                    client_process = start_client()
                    
                    print("\n🎬 Application started!")
                    print("Close the client window or press Ctrl+C to stop both processes")
                    
                    try:
                        client_process.wait()
                    except KeyboardInterrupt:
                        pass
                    finally:
                        server_process.terminate()
                        client_process.terminate()
                        print("\n🛑 Stopped server and client")
                    
                    input("\nPress Enter to return to menu...")
                    
                elif video_path:
                    print(f"❌ File not found: {video_path}")
                    input("Press Enter to continue...")
                
            elif choice == "2":
                # Use animated test pattern
                print("\n🧪 Using animated test pattern...")
                print("Note: This will show a generated animated pattern instead of real video")
                input("Press Enter to start server and client...")
                
                # Start server without video file (will use test pattern)
                server_process = start_server()
                time.sleep(2)
                client_process = start_client()
                
                print("\n🎬 Application started!")
                print("Close the client window or press Ctrl+C to stop both processes")
                
                try:
                    client_process.wait()
                except KeyboardInterrupt:
                    pass
                finally:
                    server_process.terminate()
                    client_process.terminate()
                    print("\n🛑 Stopped server and client")
                
                input("\nPress Enter to return to menu...")
                
            elif choice == "3":
                # Select from found videos
                video_files = find_video_files()
                if not video_files:
                    print("❌ No video files found in current directory")
                    input("Press Enter to continue...")
                    continue
                
                print("\nSelect a video file:")
                for i, video in enumerate(video_files, 1):
                    print(f"  {i}. {video}")
                
                try:
                    video_choice = int(input(f"\nEnter number (1-{len(video_files)}): "))
                    if 1 <= video_choice <= len(video_files):
                        selected_video = video_files[video_choice - 1]
                        print(f"\n✅ Selected: {selected_video}")
                        input("Press Enter to start server and client...")
                        
                        server_process = start_server(selected_video)
                        time.sleep(2)
                        client_process = start_client()
                        
                        print("\n🎬 Application started!")
                        print("Close the client window or press Ctrl+C to stop both processes")
                        
                        try:
                            client_process.wait()
                        except KeyboardInterrupt:
                            pass
                        finally:
                            server_process.terminate()
                            client_process.terminate()
                            print("\n🛑 Stopped server and client")
                        
                        input("\nPress Enter to return to menu...")
                    else:
                        print("❌ Invalid selection")
                        input("Press Enter to continue...")
                        
                except ValueError:
                    print("❌ Please enter a valid number")
                    input("Press Enter to continue...")
                
            elif choice == "4":
                show_help()
                input("\nPress Enter to return to menu...")
                
            else:
                print("❌ Invalid choice. Please try again.")
                input("Press Enter to continue...")
                
        except KeyboardInterrupt:
            print("\n\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"\n❌ Error: {e}")
            input("Press Enter to continue...")

if __name__ == "__main__":
    main()
