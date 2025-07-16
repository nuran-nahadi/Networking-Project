#!/usr/bin/env python3
"""
FFmpeg-based Video Streaming Server
High-performance video streaming with hardware acceleration support
"""

import socket
import threading
import time
import json
import struct
import subprocess
import os
import sys
from typing import Dict, Optional
import signal

class FFmpegVideoServer:
    def __init__(self, host='localhost', video_port=8890, control_port=8889, video_file_path=None):
        self.host = host
        self.video_port = video_port
        self.control_port = control_port
        self.video_file_path = video_file_path
        
        # Video encoding settings for different qualities
        self.quality_settings = {
            'low': {
                'resolution': '320x240',
                'bitrate': '300k',
                'fps': '15',
                'preset': 'ultrafast',
                'crf': '28'
            },
            'medium': {
                'resolution': '640x480', 
                'bitrate': '800k',
                'fps': '24',
                'preset': 'fast',
                'crf': '23'
            },
            'high': {
                'resolution': '1920x1080',
                'bitrate': '5000k', 
                'fps': '30',
                'preset': 'medium',
                'crf': '20'
            },
            'ultra': {
                'resolution': '3840x2160',
                'bitrate': '15000k',
                'fps': '30', 
                'preset': 'slow',
                'crf': '18'
            }
        }
        
        self.current_quality = 'ultra'
        self.clients = {}
        self.client_addresses = set()  # Track client addresses for UDP broadcasting
        self.is_streaming = False
        self.ffmpeg_process = None
        self.sequence_number = 0
        
        # Socket setup
        self.video_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.control_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        print(f"FFmpeg Server initialized on {host}:{video_port} (video) and {control_port} (control)")
        
    def check_ffmpeg(self):
        """Check if FFmpeg is available"""
        try:
            result = subprocess.run(['ffmpeg', '-version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                print("✅ FFmpeg found and working")
                return True
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
            
    def get_video_info(self):
        """Get video file information using FFprobe"""
        try:
            cmd = [
                'ffprobe', '-v', 'quiet', '-print_format', 'json',
                '-show_format', '-show_streams', self.video_file_path
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
            
            if result.returncode == 0:
                info = json.loads(result.stdout)
                video_stream = next((s for s in info['streams'] if s['codec_type'] == 'video'), None)
                
                if video_stream:
                    width = video_stream.get('width', 'unknown')
                    height = video_stream.get('height', 'unknown') 
                    fps = eval(video_stream.get('r_frame_rate', '30/1'))
                    duration = float(info['format'].get('duration', 0))
                    
                    print(f"Video Information:")
                    print(f"  Resolution: {width}x{height}")
                    print(f"  FPS: {fps:.2f}")
                    print(f"  Duration: {duration:.2f} seconds")
                    print(f"  Codec: {video_stream.get('codec_name', 'unknown')}")
                    
                    return True
                else:
                    print("❌ No video stream found in file")
                    return False
            else:
                print(f"❌ FFprobe failed: {result.stderr}")
                return False
                
        except Exception as e:
            print(f"❌ Error getting video info: {e}")
            return False
    
    def create_ffmpeg_command(self, quality):
        """Create FFmpeg command for streaming"""
        settings = self.quality_settings[quality]
        
        # Base FFmpeg command
        cmd = [
            'ffmpeg',
            '-re',  # Read input at native frame rate
            '-stream_loop', '-1',  # Loop the video infinitely
            '-i', self.video_file_path,  # Input file
            
            # Video encoding settings
            '-c:v', 'libx264',  # Video codec
            '-preset', settings['preset'],  # Encoding preset
            '-crf', settings['crf'],  # Constant Rate Factor (quality)
            '-b:v', settings['bitrate'],  # Video bitrate
            '-maxrate', settings['bitrate'],  # Max bitrate
            '-bufsize', str(int(settings['bitrate'].rstrip('k')) * 2) + 'k',  # Buffer size
            '-r', settings['fps'],  # Frame rate
            '-s', settings['resolution'],  # Resolution
            
            # Additional settings
            '-g', str(int(float(settings['fps'])) * 2),  # GOP size (keyframe interval)
            '-keyint_min', settings['fps'],  # Minimum keyframe interval
            '-sc_threshold', '0',  # Disable scene change detection
            
            # Audio (disable for now)
            '-an',
            
            # Output format
            '-f', 'mpegts',  # MPEG Transport Stream
            '-'  # Output to stdout
        ]
        
        return cmd
    
    def start_server(self):
        """Start the streaming server"""
        if not self.check_ffmpeg():
            return False
            
        if not os.path.exists(self.video_file_path):
            print(f"❌ Video file not found: {self.video_file_path}")
            return False
            
        if not self.get_video_info():
            return False
            
        try:
            # Start control server
            self.control_socket.bind((self.host, self.control_port))
            self.control_socket.listen(5)
            print(f"🎛️  Control server listening on {self.host}:{self.control_port}")
            
            # Start control handler thread
            control_thread = threading.Thread(target=self.handle_control_connections)
            control_thread.daemon = True
            control_thread.start()
            
            self.is_streaming = True
            self.start_ffmpeg_streaming()
            
        except Exception as e:
            print(f"❌ Error starting server: {e}")
            return False
    
    def start_ffmpeg_streaming(self):
        """Start FFmpeg streaming process"""
        print(f"🎬 Starting FFmpeg stream with quality: {self.current_quality}")
        
        while self.is_streaming:
            try:
                # Create FFmpeg command
                cmd = self.create_ffmpeg_command(self.current_quality)
                print(f"🔧 FFmpeg command: {' '.join(cmd[:10])}...")
                
                # Start FFmpeg process
                self.ffmpeg_process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.PIPE,
                    bufsize=0
                )
                
                print(f"✅ FFmpeg process started (PID: {self.ffmpeg_process.pid})")
                
                # Read and broadcast data
                self.stream_data()
                
            except Exception as e:
                print(f"❌ FFmpeg streaming error: {e}")
                time.sleep(1)  # Wait before retrying
    
    def stream_data(self):
        """Read from FFmpeg and send to clients"""
        chunk_size = 1316  # UDP safe size (1500 - IP header - UDP header - our header)
        packets_sent = 0
        last_status_time = time.time()
        
        try:
            while self.is_streaming and self.ffmpeg_process and self.ffmpeg_process.poll() is None:
                # Read chunk from FFmpeg
                data = self.ffmpeg_process.stdout.read(chunk_size)
                
                if not data:
                    print("📺 Video ended, restarting...")
                    break
                
                # Create packet with header
                packet = self.create_packet(data)
                
                # Broadcast to clients
                self.broadcast_packet(packet)
                packets_sent += 1
                
                # Status update every 5 seconds
                current_time = time.time()
                if current_time - last_status_time >= 5.0:
                    print(f"📡 Streaming: {packets_sent} packets sent, {len(self.client_addresses)} clients connected")
                    packets_sent = 0
                    last_status_time = current_time
                
                # Small delay to prevent overwhelming the network
                time.sleep(0.001)  # 1ms delay
                
        except Exception as e:
            print(f"❌ Streaming error: {e}")
        finally:
            if self.ffmpeg_process:
                self.ffmpeg_process.terminate()
                self.ffmpeg_process.wait()
    
    def create_packet(self, data):
        """Create packet with header information"""
        timestamp = time.time()
        quality_bytes = self.current_quality.encode()
        
        # Header: sequence(4) + timestamp(8) + quality_len(1) + quality + data_len(4) + data
        header = struct.pack('!I', self.sequence_number)  # sequence number
        header += struct.pack('!d', timestamp)  # timestamp
        header += struct.pack('!B', len(quality_bytes))  # quality length
        header += quality_bytes  # quality string
        header += struct.pack('!I', len(data))  # data length
        
        self.sequence_number += 1
        return header + data
    
    def broadcast_packet(self, packet):
        """Send packet to all connected clients"""
        if not self.client_addresses:
            return  # No clients connected
            
        for client_addr in list(self.client_addresses):  # Copy to avoid modification during iteration
            try:
                self.video_socket.sendto(packet, client_addr)
            except Exception as e:
                # Remove failed client
                print(f"❌ Failed to send to {client_addr}, removing: {e}")
                self.client_addresses.discard(client_addr)
    
    def handle_control_connections(self):
        """Handle control connections for quality changes"""
        while self.is_streaming:
            try:
                client_socket, addr = self.control_socket.accept()
                print(f"🔗 Control connection from {addr}")
                
                # Handle client in separate thread
                client_thread = threading.Thread(
                    target=self.handle_client_control,
                    args=(client_socket, addr)
                )
                client_thread.daemon = True
                client_thread.start()
                
            except Exception as e:
                if self.is_streaming:
                    print(f"❌ Control connection error: {e}")
    
    def handle_client_control(self, client_socket, addr):
        """Handle control messages from a client"""
        client_video_addr = None
        
        try:
            while self.is_streaming:
                data = client_socket.recv(1024).decode()
                if not data:
                    break
                
                try:
                    message = json.loads(data)
                    
                    if message['type'] == 'client_register':
                        # Register client for video broadcasting
                        client_video_port = message['video_port']
                        client_video_addr = (addr[0], client_video_port)
                        self.client_addresses.add(client_video_addr)
                        print(f"📡 Registered client for video stream: {client_video_addr}")
                        
                        # Send acknowledgment
                        response = {
                            'type': 'register_ack',
                            'status': 'success',
                            'timestamp': time.time()
                        }
                        client_socket.send(json.dumps(response).encode())
                    
                    elif message['type'] == 'quality_request':
                        requested_quality = message['quality']
                        
                        if requested_quality in self.quality_settings:
                            old_quality = self.current_quality
                            self.current_quality = requested_quality
                            
                            print(f"🎯 Quality change: {old_quality} → {requested_quality}")
                            
                            # Send acknowledgment
                            response = {
                                'type': 'quality_ack',
                                'quality': requested_quality,
                                'timestamp': time.time()
                            }
                            client_socket.send(json.dumps(response).encode())
                            
                            # Restart FFmpeg with new quality
                            self.restart_ffmpeg()
                        
                except json.JSONDecodeError:
                    print(f"❌ Invalid JSON from {addr}")
                    
        except Exception as e:
            print(f"❌ Client control error {addr}: {e}")
        finally:
            # Unregister client when disconnecting
            if client_video_addr:
                self.client_addresses.discard(client_video_addr)
                print(f"📡 Unregistered client: {client_video_addr}")
            
            client_socket.close()
            if addr in self.clients:
                del self.clients[addr]
    
    def restart_ffmpeg(self):
        """Restart FFmpeg with new quality settings"""
        if self.ffmpeg_process:
            print("🔄 Restarting FFmpeg with new quality...")
            self.ffmpeg_process.terminate()
            self.ffmpeg_process.wait()
            # The main streaming loop will restart FFmpeg automatically
    
    def cleanup(self):
        """Clean up resources"""
        print("🧹 Cleaning up server...")
        self.is_streaming = False
        
        if self.ffmpeg_process:
            self.ffmpeg_process.terminate()
            try:
                self.ffmpeg_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.ffmpeg_process.kill()
        
        self.video_socket.close()
        self.control_socket.close()
        print("✅ Server cleanup completed")

def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    print("\n🛑 Received interrupt signal...")
    sys.exit(0)

def find_video_in_current_directory():
    """Find video files in the current directory only"""
    print("🔍 Searching for video files in current directory...")
    
    video_extensions = ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v']
    current_dir = os.getcwd()
    found_videos = []
    
    try:
        for file in os.listdir(current_dir):
            if any(file.lower().endswith(ext) for ext in video_extensions):
                full_path = os.path.join(current_dir, file)
                if os.path.isfile(full_path):
                    size_mb = os.path.getsize(full_path) / (1024 * 1024)
                    found_videos.append((full_path, size_mb, file))
                    print(f"   📹 {file} ({size_mb:.1f} MB)")
    except PermissionError:
        print(f"❌ Permission denied accessing current directory")
        return None
    
    if found_videos:
        print(f"\n✅ Found {len(found_videos)} video file(s) in current directory")
        
        if len(found_videos) == 1:
            # Auto-select if only one video found
            selected_video = found_videos[0][0]
            print(f"🎯 Auto-selected: {found_videos[0][2]}")
            return selected_video
        else:
            # Let user choose from multiple videos
            print("\n📋 Select a video file:")
            for i, (path, size_mb, filename) in enumerate(found_videos, 1):
                print(f"   {i}. {filename} ({size_mb:.1f} MB)")
            
            while True:
                try:
                    choice = input(f"\nEnter choice (1-{len(found_videos)}) or 'q' to quit: ").strip()
                    if choice.lower() == 'q':
                        return None
                    
                    choice_idx = int(choice) - 1
                    if 0 <= choice_idx < len(found_videos):
                        selected_video = found_videos[choice_idx][0]
                        print(f"🎯 Selected: {found_videos[choice_idx][2]}")
                        return selected_video
                    else:
                        print(f"❌ Please enter a number between 1 and {len(found_videos)}")
                except ValueError:
                    print("❌ Please enter a valid number")
    else:
        print("❌ No video files found in current directory")
        print("💡 Please place a video file (.mp4, .avi, .mkv, etc.) in the current directory")
        return None

def main():
    import sys
    
    # Set up signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    # Get video file path
    video_file = None
    if len(sys.argv) > 1:
        video_file = sys.argv[1]
        if not os.path.exists(video_file):
            print(f"❌ Video file '{video_file}' not found!")
            print("Usage: python server_ffmpeg.py [path_to_video.mp4]")
            return
    else:
        print("🎬 FFmpeg Video Streaming Server")
        print("=" * 40)
        
        # Auto-detect video files in current directory
        video_file = find_video_in_current_directory()
        if not video_file:
            print("\n❌ No video file selected or found!")
            return
    
    server = FFmpegVideoServer(video_file_path=video_file)
    try:
        server.start_server()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down server...")
    finally:
        server.cleanup()

if __name__ == "__main__":
    main()
