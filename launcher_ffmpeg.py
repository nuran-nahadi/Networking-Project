#!/usr/bin/env python3
"""
FFmpeg Video Streaming System Launcher
Easy-to-use launcher for both server and client components
"""

import os
import sys
import subprocess
import threading
import time
import signal
from pathlib import Path

class StreamingLauncher:
    def __init__(self):
        self.server_process = None
        self.client_process = None
        self.is_running = False
        
        # Get the directory where this script is located
        self.script_dir = Path(__file__).parent.absolute()
        self.server_script = self.script_dir / "server_ffmpeg.py"
        self.client_script = self.script_dir / "client_ffmpeg.py"
        
    def check_dependencies(self):
        """Check if all required files and dependencies are available"""
        print("[CHECK] Checking dependencies...")
        
        # Check if scripts exist
        if not self.server_script.exists():
            print(f"[ERROR] Server script not found: {self.server_script}")
            return False
            
        if not self.client_script.exists():
            print(f"[ERROR] Client script not found: {self.client_script}")
            return False
        
        # Check FFmpeg
        try:
            result = subprocess.run(['ffmpeg', '-version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                print("[OK] FFmpeg found")
            else:
                print("❌ FFmpeg not working properly")
                return False
        except FileNotFoundError:
            print("❌ FFmpeg not found in PATH")
            print("Please install FFmpeg from https://ffmpeg.org/download.html")
            return False
        except subprocess.TimeoutExpired:
            print("❌ FFmpeg check timed out")
            return False
        
        # Check FFplay
        try:
            result = subprocess.run(['ffplay', '-version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                print("✅ FFplay found")
            else:
                print("❌ FFplay not working properly")
                return False
        except FileNotFoundError:
            print("❌ FFplay not found in PATH")
            print("Please install FFmpeg (includes FFplay) from https://ffmpeg.org/download.html")
            return False
        except subprocess.TimeoutExpired:
            print("❌ FFplay check timed out")
            return False
        
        print("✅ All dependencies found")
        return True
    
    def get_video_files(self):
        """Find video files in common locations"""
        video_extensions = {'.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v'}
        video_files = []
        
        # Search in current directory
        for file in self.script_dir.iterdir():
            if file.is_file() and file.suffix.lower() in video_extensions:
                video_files.append(file)
        
        # Search in common video directories
        common_dirs = [
            Path.home() / "Videos",
            Path.home() / "Downloads", 
            Path.home() / "Desktop",
        ]
        
        for dir_path in common_dirs:
            if dir_path.exists():
                for file in dir_path.rglob("*"):
                    if file.is_file() and file.suffix.lower() in video_extensions:
                        video_files.append(file)
                        if len(video_files) >= 20:  # Limit to 20 files
                            break
            if len(video_files) >= 20:
                break
        
        return sorted(set(video_files))[:20]  # Remove duplicates and limit
    
    def select_video_file(self):
        """Interactive video file selection"""
        print("\n📁 Video File Selection")
        print("=" * 40)
        
        # Option 1: Manual path entry
        print("1. Enter video file path manually")
        
        # Option 2: Auto-detected files
        video_files = self.get_video_files()
        if video_files:
            print("2. Choose from detected video files:")
            for i, file in enumerate(video_files, 3):
                print(f"   {i}. {file.name} ({file.parent})")
        
        print()
        try:
            choice = input("Select option (1 for manual entry, or number for detected file): ").strip()
            
            if choice == "1":
                video_path = input("Enter full path to video file: ").strip().strip('"\'')
                if not video_path:
                    print("❌ No path entered")
                    return None
                
                video_file = Path(video_path)
                if not video_file.exists():
                    print(f"❌ File not found: {video_file}")
                    return None
                
                return video_file
            
            elif choice.isdigit():
                choice_idx = int(choice) - 3
                if 0 <= choice_idx < len(video_files):
                    return video_files[choice_idx]
                else:
                    print("❌ Invalid selection")
                    return None
            else:
                print("❌ Invalid choice")
                return None
                
        except KeyboardInterrupt:
            print("\n❌ Selection cancelled")
            return None
        except Exception as e:
            print(f"❌ Error: {e}")
            return None
    
    def show_main_menu(self):
        """Show the main menu"""
        print("\n" + "="*50)
        print("🎬 FFmpeg Video Streaming System Launcher")
        print("="*50)
        print("1. 🚀 Quick Start (Server + Client)")
        print("2. 🖥️  Start Server Only")
        print("3. 📺 Start Client Only")
        print("4. 🎮 Start Both Separately")
        print("5. ℹ️  System Information")
        print("6. ❌ Exit")
        print("="*50)
    
    def show_system_info(self):
        """Display system information"""
        print("\n📊 System Information")
        print("=" * 30)
        
        # Python version
        print(f"🐍 Python: {sys.version.split()[0]}")
        
        # FFmpeg version
        try:
            result = subprocess.run(['ffmpeg', '-version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                ffmpeg_line = result.stdout.split('\n')[0]
                print(f"🎬 {ffmpeg_line}")
            else:
                print("❌ FFmpeg: Not working")
        except:
            print("❌ FFmpeg: Not found")
        
        # Script locations
        print(f"📁 Scripts Directory: {self.script_dir}")
        print(f"🖥️  Server Script: {'✅' if self.server_script.exists() else '❌'}")
        print(f"📺 Client Script: {'✅' if self.client_script.exists() else '❌'}")
        
        # Video files
        video_files = self.get_video_files()
        print(f"🎥 Video Files Found: {len(video_files)}")
        
        input("\nPress Enter to continue...")
    
    def start_server(self, video_file, wait_for_startup=True):
        """Start the server process"""
        try:
            print(f"🖥️  Starting server with video: {video_file.name}")
            
            cmd = [sys.executable, str(self.server_script), str(video_file)]
            self.server_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            if wait_for_startup:
                # Wait a moment for server to start
                time.sleep(2)
                
                # Check if server is still running
                if self.server_process.poll() is not None:
                    print("❌ Server failed to start")
                    return False
            
            # Start thread to monitor server output
            server_thread = threading.Thread(
                target=self.monitor_process, 
                args=(self.server_process, "SERVER")
            )
            server_thread.daemon = True
            server_thread.start()
            
            print("✅ Server started successfully")
            return True
            
        except Exception as e:
            print(f"❌ Error starting server: {e}")
            return False
    
    def start_client(self, wait_for_startup=True):
        """Start the client process"""
        try:
            print("📺 Starting client...")
            
            cmd = [sys.executable, str(self.client_script)]
            self.client_process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )
            
            if wait_for_startup:
                # Wait a moment for client to start
                time.sleep(2)
                
                # Check if client is still running
                if self.client_process.poll() is not None:
                    print("❌ Client failed to start")
                    return False
            
            # Start thread to monitor client output
            client_thread = threading.Thread(
                target=self.monitor_process, 
                args=(self.client_process, "CLIENT")
            )
            client_thread.daemon = True
            client_thread.start()
            
            print("✅ Client started successfully")
            return True
            
        except Exception as e:
            print(f"❌ Error starting client: {e}")
            return False
    
    def monitor_process(self, process, name):
        """Monitor process output"""
        try:
            while process.poll() is None:
                line = process.stdout.readline()
                if line:
                    print(f"[{name}] {line.rstrip()}")
        except Exception as e:
            print(f"❌ Error monitoring {name}: {e}")
    
    def quick_start(self):
        """Quick start both server and client"""
        print("\n🚀 Quick Start Mode")
        print("=" * 20)
        
        # Select video file
        video_file = self.select_video_file()
        if not video_file:
            return
        
        print(f"\n📺 Selected video: {video_file.name}")
        print("🎬 Starting server and client...")
        
        # Start server
        if not self.start_server(video_file):
            return
        
        # Wait a bit for server to initialize
        print("⏳ Waiting for server to initialize...")
        time.sleep(3)
        
        # Start client
        if not self.start_client():
            self.stop_all()
            return
        
        self.is_running = True
        
        print("\n✅ Both server and client are running!")
        print("📺 Video should start playing shortly...")
        print("Press Ctrl+C to stop both processes")
        
        try:
            # Wait for processes
            while self.is_running:
                if self.server_process and self.server_process.poll() is not None:
                    print("❌ Server process ended")
                    break
                if self.client_process and self.client_process.poll() is not None:
                    print("❌ Client process ended")
                    break
                time.sleep(1)
        except KeyboardInterrupt:
            print("\n🛑 Stopping processes...")
        finally:
            self.stop_all()
    
    def start_server_only(self):
        """Start only the server"""
        print("\n🖥️  Server Only Mode")
        print("=" * 20)
        
        video_file = self.select_video_file()
        if not video_file:
            return
        
        if not self.start_server(video_file, wait_for_startup=False):
            return
        
        print("\n✅ Server is running!")
        print("🔗 Clients can now connect to localhost:8890")
        print("Press Ctrl+C to stop the server")
        
        try:
            self.server_process.wait()
        except KeyboardInterrupt:
            print("\n🛑 Stopping server...")
            self.stop_server()
    
    def start_client_only(self):
        """Start only the client"""
        print("\n📺 Client Only Mode")
        print("=" * 20)
        print("🔗 Connecting to server at localhost:8890...")
        
        if not self.start_client(wait_for_startup=False):
            return
        
        print("\n✅ Client is running!")
        print("📺 Video should start playing if server is available")
        print("Press Ctrl+C to stop the client")
        
        try:
            self.client_process.wait()
        except KeyboardInterrupt:
            print("\n🛑 Stopping client...")
            self.stop_client()
    
    def start_both_separately(self):
        """Start both with separate terminals (Windows/Linux)"""
        print("\n🎮 Separate Terminals Mode")
        print("=" * 30)
        
        video_file = self.select_video_file()
        if not video_file:
            return
        
        try:
            # Determine the platform and open terminals accordingly
            if sys.platform == "win32":
                # Windows
                server_cmd = f'start "FFmpeg Server" cmd /k "python {self.server_script} {video_file}"'
                client_cmd = f'start "FFmpeg Client" cmd /k "python {self.client_script}"'
                
                os.system(server_cmd)
                time.sleep(2)  # Wait for server to start
                os.system(client_cmd)
                
            elif sys.platform == "darwin":
                # macOS
                server_cmd = f'osascript -e \'tell app "Terminal" to do script "cd {self.script_dir} && python {self.server_script} {video_file}"\''
                client_cmd = f'osascript -e \'tell app "Terminal" to do script "cd {self.script_dir} && python {self.client_script}"\''
                
                os.system(server_cmd)
                time.sleep(2)
                os.system(client_cmd)
                
            else:
                # Linux
                # Try different terminal emulators
                terminals = ['gnome-terminal', 'konsole', 'xterm', 'terminator']
                
                terminal_found = False
                for terminal in terminals:
                    try:
                        subprocess.run(['which', terminal], check=True, capture_output=True)
                        
                        if terminal == 'gnome-terminal':
                            subprocess.Popen([terminal, '--', 'python', str(self.server_script), str(video_file)])
                            time.sleep(2)
                            subprocess.Popen([terminal, '--', 'python', str(self.client_script)])
                        elif terminal == 'konsole':
                            subprocess.Popen([terminal, '-e', 'python', str(self.server_script), str(video_file)])
                            time.sleep(2)
                            subprocess.Popen([terminal, '-e', 'python', str(self.client_script)])
                        else:
                            subprocess.Popen([terminal, '-e', f'python {self.server_script} {video_file}'])
                            time.sleep(2)
                            subprocess.Popen([terminal, '-e', f'python {self.client_script}'])
                        
                        terminal_found = True
                        break
                        
                    except subprocess.CalledProcessError:
                        continue
                
                if not terminal_found:
                    print("❌ No suitable terminal emulator found")
                    print("Please install gnome-terminal, konsole, or xterm")
                    return
            
            print("✅ Server and client launched in separate terminals!")
            print("📺 Video should start playing shortly...")
            
        except Exception as e:
            print(f"❌ Error launching terminals: {e}")
            print("You may need to start the server and client manually:")
            print(f"Server: python {self.server_script} {video_file}")
            print(f"Client: python {self.client_script}")
    
    def stop_server(self):
        """Stop the server process"""
        if self.server_process:
            try:
                self.server_process.terminate()
                self.server_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.server_process.kill()
            except Exception as e:
                print(f"Error stopping server: {e}")
            finally:
                self.server_process = None
    
    def stop_client(self):
        """Stop the client process"""
        if self.client_process:
            try:
                self.client_process.terminate()
                self.client_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.client_process.kill()
            except Exception as e:
                print(f"Error stopping client: {e}")
            finally:
                self.client_process = None
    
    def stop_all(self):
        """Stop all processes"""
        self.is_running = False
        self.stop_server()
        self.stop_client()
        print("✅ All processes stopped")
    
    def run(self):
        """Main launcher loop"""
        print("🎬 FFmpeg Video Streaming System Launcher")
        
        # Check dependencies first
        if not self.check_dependencies():
            print("\n❌ Please install missing dependencies and try again")
            return
        
        # Set up signal handler for graceful shutdown
        def signal_handler(signum, frame):
            print("\n🛑 Received interrupt signal...")
            self.stop_all()
            sys.exit(0)
        
        signal.signal(signal.SIGINT, signal_handler)
        
        while True:
            try:
                self.show_main_menu()
                choice = input("\nSelect option (1-6): ").strip()
                
                if choice == "1":
                    self.quick_start()
                elif choice == "2":
                    self.start_server_only()
                elif choice == "3":
                    self.start_client_only()
                elif choice == "4":
                    self.start_both_separately()
                elif choice == "5":
                    self.show_system_info()
                elif choice == "6":
                    print("👋 Goodbye!")
                    break
                else:
                    print("❌ Invalid choice. Please select 1-6.")
                
            except KeyboardInterrupt:
                print("\n👋 Goodbye!")
                break
            except Exception as e:
                print(f"❌ Error: {e}")
        
        # Clean up on exit
        self.stop_all()

def main():
    launcher = StreamingLauncher()
    launcher.run()

if __name__ == "__main__":
    main()
