#!/usr/bin/env python3
"""
FFmpeg-based Video Streaming Client
High-performance video playback with adaptive quality
"""

import socket
import threading
import time
import json
import struct
import subprocess
import os
import sys
import signal
from collections import deque
import statistics

class NetworkMonitor:
    def __init__(self, window_size=100):
        self.window_size = window_size
        self.packet_times = deque(maxlen=window_size)
        self.packet_sizes = deque(maxlen=window_size)
        self.sequence_numbers = deque(maxlen=window_size)
        self.latencies = deque(maxlen=window_size)
        
        # Network metrics
        self.packet_loss_rate = 0.0
        self.jitter = 0.0
        self.average_latency = 0.0
        self.throughput = 0.0
        
        self.last_sequence = -1
        self.lost_packets = 0
        self.total_packets = 0
        
    def add_packet(self, sequence_num, timestamp, packet_size):
        """Add packet information for analysis"""
        current_time = time.time()
        
        # Calculate latency
        latency = (current_time - timestamp) * 1000  # Convert to milliseconds
        
        self.packet_times.append(current_time)
        self.packet_sizes.append(packet_size)
        self.sequence_numbers.append(sequence_num)
        self.latencies.append(latency)
        
        # Check for packet loss
        self.total_packets += 1
        if self.last_sequence >= 0:
            expected_seq = self.last_sequence + 1
            if sequence_num > expected_seq:
                lost = sequence_num - expected_seq
                self.lost_packets += lost
                print(f"📦 Packet loss detected: {lost} packets lost")
        
        self.last_sequence = sequence_num
        self.update_metrics()
    
    def update_metrics(self):
        """Update network performance metrics"""
        if len(self.packet_times) < 2:
            return
        
        # Calculate packet loss rate
        if self.total_packets > 0:
            self.packet_loss_rate = (self.lost_packets / self.total_packets) * 100
        
        # Calculate average latency
        if self.latencies:
            self.average_latency = statistics.mean(self.latencies)
        
        # Calculate jitter
        if len(self.latencies) >= 2:
            latency_diffs = [abs(self.latencies[i] - self.latencies[i-1]) 
                           for i in range(1, len(self.latencies))]
            if latency_diffs:
                self.jitter = statistics.mean(latency_diffs)
        
        # Calculate throughput
        if len(self.packet_times) >= 2:
            time_window = self.packet_times[-1] - self.packet_times[0]
            if time_window > 0:
                total_bytes = sum(self.packet_sizes)
                self.throughput = total_bytes / time_window
    
    def get_metrics(self):
        """Return current network metrics"""
        return {
            'latency': self.average_latency,
            'jitter': self.jitter,
            'packet_loss': self.packet_loss_rate,
            'throughput': self.throughput
        }

class QualityAdaptationEngine:
    def __init__(self):
        self.current_quality = 'ultra'
        self.quality_history = deque(maxlen=50)
        
        # Thresholds for quality switching
        self.thresholds = {
            'latency_high': 200,      # ms
            'latency_low': 50,        # ms
            'jitter_high': 50,        # ms
            'packet_loss_high': 2.0,  # %
            'throughput_low': 50000,  # bytes/sec
            'throughput_high': 200000 # bytes/sec
        }
        
        self.last_adaptation_time = 0
        self.adaptation_cooldown = 3.0  # seconds
    
    def should_adapt_quality(self, metrics):
        """Determine if quality should be changed based on network metrics"""
        current_time = time.time()
        
        # Prevent too frequent adaptations
        if current_time - self.last_adaptation_time < self.adaptation_cooldown:
            return self.current_quality
        
        latency = metrics.get('latency', 0)
        jitter = metrics.get('jitter', 0)
        packet_loss = metrics.get('packet_loss', 0)
        throughput = metrics.get('throughput', 0)
        
        new_quality = self.current_quality
        
        # Decision logic for quality adaptation
        if (latency > self.thresholds['latency_high'] or 
            jitter > self.thresholds['jitter_high'] or 
            packet_loss > self.thresholds['packet_loss_high'] or
            throughput < self.thresholds['throughput_low']):
            
            # Network conditions are poor, decrease quality
            if self.current_quality == 'ultra':
                new_quality = 'high'
            elif self.current_quality == 'high':
                new_quality = 'medium'
            elif self.current_quality == 'medium':
                new_quality = 'low'
            
        elif (latency < self.thresholds['latency_low'] and 
              jitter < self.thresholds['jitter_high'] / 2 and 
              packet_loss < self.thresholds['packet_loss_high'] / 2 and
              throughput > self.thresholds['throughput_high']):
            
            # Network conditions are good, increase quality
            if self.current_quality == 'low':
                new_quality = 'medium'
            elif self.current_quality == 'medium':
                new_quality = 'high'
            elif self.current_quality == 'high':
                new_quality = 'ultra'
        
        if new_quality != self.current_quality:
            print(f"🎯 Quality adaptation: {self.current_quality} → {new_quality}")
            print(f"📊 Metrics: Latency={latency:.1f}ms, Jitter={jitter:.1f}ms, "
                  f"Loss={packet_loss:.1f}%, Throughput={throughput:.0f}B/s")
            
            self.current_quality = new_quality
            self.last_adaptation_time = current_time
            self.quality_history.append((current_time, new_quality))
        
        return self.current_quality

class FFmpegVideoClient:
    def __init__(self, server_host='localhost', video_port=8890, control_port=8889):
        self.server_host = server_host
        self.video_port = video_port
        self.control_port = control_port
        
        # Components
        self.network_monitor = NetworkMonitor()
        self.adaptation_engine = QualityAdaptationEngine()
        
        # Sockets
        self.video_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.control_socket = None
        
        # FFmpeg process for playback
        self.ffplay_process = None
        self.ffplay_pipe = None
        
        # State
        self.is_running = False
        self.current_quality = 'ultra'
        self.received_quality = None
        
        # Buffer for received data
        self.video_buffer = deque(maxlen=1000)  # Buffer for smooth playback
        
        print(f"🎬 FFmpeg Client initialized for server {server_host}:{video_port}")
    
    def check_ffmpeg(self):
        """Check if FFmpeg/FFplay is available"""
        try:
            # Check FFplay
            result = subprocess.run(['ffplay', '-version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                print("✅ FFplay found and working")
                return True
            else:
                print("❌ FFplay not working properly")
                return False
        except FileNotFoundError:
            print("❌ FFplay not found in PATH")
            print("Please install FFmpeg from https://ffmpeg.org/download.html")
            return False
        except subprocess.TimeoutExpired:
            print("❌ FFplay check timed out")
            return False
    
    def connect_to_server(self):
        """Establish connection to server"""
        try:
            # Bind video socket to any available port (let OS choose)
            self.video_socket.bind(('', 0))  # 0 means any available port
            actual_port = self.video_socket.getsockname()[1]
            print(f"📺 Video socket bound to port {actual_port}")
            
            # Connect control socket
            self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.control_socket.connect((self.server_host, self.control_port))
            print(f"🔗 Connected to control server at {self.server_host}:{self.control_port}")
            
            # Send client registration with video port
            registration = {
                'type': 'client_register',
                'video_port': actual_port,
                'timestamp': time.time()
            }
            self.control_socket.send(json.dumps(registration).encode())
            
            # Wait for registration acknowledgment
            response = self.control_socket.recv(1024).decode()
            ack = json.loads(response)
            if ack['type'] == 'register_ack' and ack['status'] == 'success':
                print(f"✅ Successfully registered with server for video on port {actual_port}")
            else:
                print(f"❌ Registration failed: {ack}")
                return False
            
            return True
            
        except Exception as e:
            print(f"❌ Error connecting to server: {e}")
            return False
    
    def send_quality_request(self, quality):
        """Send quality change request to server"""
        if self.control_socket:
            try:
                message = {
                    'type': 'quality_request',
                    'quality': quality,
                    'timestamp': time.time()
                }
                self.control_socket.send(json.dumps(message).encode())
                
                # Wait for acknowledgment
                response = self.control_socket.recv(1024).decode()
                ack = json.loads(response)
                if ack['type'] == 'quality_ack':
                    print(f"✅ Quality change acknowledged: {ack['quality']}")
                    return True
                    
            except Exception as e:
                print(f"❌ Error sending quality request: {e}")
        
        return False
    
    def parse_packet(self, data):
        """Parse incoming video packet"""
        try:
            offset = 0
            
            # Parse header
            sequence_num = struct.unpack('!I', data[offset:offset+4])[0]
            offset += 4
            
            timestamp = struct.unpack('!d', data[offset:offset+8])[0]
            offset += 8
            
            quality_len = struct.unpack('!B', data[offset:offset+1])[0]
            offset += 1
            
            quality = data[offset:offset+quality_len].decode()
            offset += quality_len
            
            data_len = struct.unpack('!I', data[offset:offset+4])[0]
            offset += 4
            
            # Extract video data
            video_data = data[offset:offset+data_len]
            
            return sequence_num, timestamp, quality, video_data
            
        except Exception as e:
            print(f"❌ Error parsing packet: {e}")
            return None, None, None, None
    
    def start_ffplay(self):
        """Start FFplay process for video playback"""
        try:
            cmd = [
                'ffplay',
                '-f', 'mpegts',          # Input format
                '-i', '-',               # Read from stdin
                '-autoexit',             # Exit when playback finishes
                '-x', '1600',            # Window width
                '-y', '900',             # Window height
                '-window_title', 'FFmpeg Video Stream',
                '-left', '0',            # Window position
                '-top', '0',
                '-fast',                 # Fast decoding
                '-sync', 'video',        # Sync to video
                '-framedrop',            # Drop frames if needed
                '-infbuf',               # Infinite buffer
                '-probesize', '32',      # Small probe size for faster startup
                '-analyzeduration', '0', # Skip analysis for faster startup
                '-fflags', 'nobuffer',   # No buffering
                '-flags', 'low_delay',   # Low delay
                '-avioflags', 'direct',  # Direct I/O
                '-loglevel', 'quiet'     # Quiet output
            ]
            
            print("🎮 Starting FFplay for video playback...")
            self.ffplay_process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stderr=subprocess.PIPE,
                bufsize=0
            )
            
            self.ffplay_pipe = self.ffplay_process.stdin
            print(f"✅ FFplay started (PID: {self.ffplay_process.pid})")
            return True
            
        except Exception as e:
            print(f"❌ Error starting FFplay: {e}")
            return False
    
    def start_streaming(self):
        """Start the video streaming client"""
        if not self.check_ffmpeg():
            return
            
        if not self.connect_to_server():
            return
        
        if not self.start_ffplay():
            return
        
        self.is_running = True
        
        # Start video receiving thread
        video_thread = threading.Thread(target=self.receive_video)
        video_thread.daemon = True
        video_thread.start()
        
        # Start video playback thread
        playback_thread = threading.Thread(target=self.playback_video)
        playback_thread.daemon = True
        playback_thread.start()
        
        # Main loop for quality adaptation
        try:
            print("\n🎥 Starting FFmpeg video streaming client...")
            print("📊 Monitoring network metrics and adapting quality...")
            print("Press Ctrl+C to stop\n")
            
            while self.is_running:
                time.sleep(1.0)  # Check every second
                
                # Get current network metrics
                metrics = self.network_monitor.get_metrics()
                
                # Print status
                if self.received_quality:
                    quality_map = {
                        'low': '320x240',
                        'medium': '640x480',
                        'high': '1920x1080',
                        'ultra': '3840x2160'
                    }
                    resolution = quality_map.get(self.received_quality, 'unknown')
                    
                    print(f"📺 Display: 1600x900 | Stream: {self.received_quality}({resolution}) | "
                          f"Loss: {metrics['packet_loss']:.1f}% | "
                          f"Latency: {metrics['latency']:.1f}ms | "
                          f"Buffer: {len(self.video_buffer)}")
                
                # Check if quality should be adapted
                new_quality = self.adaptation_engine.should_adapt_quality(metrics)
                
                if new_quality != self.current_quality:
                    if self.send_quality_request(new_quality):
                        self.current_quality = new_quality
                
        except KeyboardInterrupt:
            print("\n🛑 Stopping client...")
        finally:
            self.cleanup()
    
    def receive_video(self):
        """Receive video packets from server"""
        print("📡 Starting video reception...")
        
        while self.is_running:
            try:
                data, addr = self.video_socket.recvfrom(65536)  # Max UDP packet size
                
                # Parse packet
                seq_num, timestamp, quality, video_data = self.parse_packet(data)
                
                if video_data is not None:
                    # Update network monitoring
                    self.network_monitor.add_packet(seq_num, timestamp, len(data))
                    
                    # Track received quality
                    if quality != self.received_quality:
                        if self.received_quality is not None:
                            print(f"📺 Stream quality changed: {self.received_quality} → {quality}")
                        self.received_quality = quality
                    
                    # Add to buffer
                    self.video_buffer.append(video_data)
                
            except Exception as e:
                if self.is_running:
                    print(f"❌ Error receiving video: {e}")
    
    def playback_video(self):
        """Send buffered video data to FFplay"""
        print("🎮 Starting video playback...")
        
        while self.is_running:
            try:
                if self.video_buffer and self.ffplay_pipe:
                    # Get data from buffer
                    video_data = self.video_buffer.popleft()
                    
                    # Send to FFplay
                    self.ffplay_pipe.write(video_data)
                    self.ffplay_pipe.flush()
                else:
                    # No data available, wait a bit
                    time.sleep(0.001)  # 1ms
                    
            except BrokenPipeError:
                print("🎮 FFplay window closed")
                self.is_running = False
                break
            except Exception as e:
                if self.is_running:
                    print(f"❌ Playback error: {e}")
                break
    
    def cleanup(self):
        """Clean up resources"""
        print("🧹 Cleaning up client...")
        self.is_running = False
        
        # Close FFplay
        if self.ffplay_pipe:
            try:
                self.ffplay_pipe.close()
            except:
                pass
        
        if self.ffplay_process:
            self.ffplay_process.terminate()
            try:
                self.ffplay_process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self.ffplay_process.kill()
        
        # Close sockets
        if self.video_socket:
            self.video_socket.close()
        
        if self.control_socket:
            self.control_socket.close()
        
        print("✅ Client cleanup completed")

def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    print("\n🛑 Received interrupt signal...")
    sys.exit(0)

def main():
    # Set up signal handler
    signal.signal(signal.SIGINT, signal_handler)
    
    client = FFmpegVideoClient()
    try:
        client.start_streaming()
    except KeyboardInterrupt:
        print("\n🛑 Shutting down client...")
    finally:
        client.cleanup()

if __name__ == "__main__":
    main()
