import socket
import threading
import time
import cv2
import json
import struct
import numpy as np
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
        
        # Calculate latency (assuming timestamp is from server)
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
                print(f"Packet loss detected: {lost} packets lost")
        
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
        
        # Calculate jitter (variation in latency)
        if len(self.latencies) >= 2:
            latency_diffs = [abs(self.latencies[i] - self.latencies[i-1]) 
                           for i in range(1, len(self.latencies))]
            if latency_diffs:
                self.jitter = statistics.mean(latency_diffs)
        
        # Calculate throughput (bytes per second)
        if len(self.packet_times) >= 2:
            time_window = self.packet_times[-1] - self.packet_times[0]
            if time_window > 0:
                total_bytes = sum(self.packet_sizes)
                self.throughput = total_bytes / time_window  # bytes per second
    
    def get_metrics(self):
        """Return current network metrics"""
        return {
            'latency': self.average_latency,
            'jitter': self.jitter,
            'packet_loss': self.packet_loss_rate,
            'throughput': self.throughput
        }

class ResolutionAdaptationEngine:
    def __init__(self):
        self.current_resolution = '1080p'
        self.resolution_history = deque(maxlen=50)
        
        # Thresholds for resolution switching
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
    
    def should_adapt_resolution(self, metrics):
        """Determine if resolution should be changed based on network metrics"""
        current_time = time.time()
        
        # Prevent too frequent adaptations
        if current_time - self.last_adaptation_time < self.adaptation_cooldown:
            return self.current_resolution
        
        latency = metrics.get('latency', 0)
        jitter = metrics.get('jitter', 0)
        packet_loss = metrics.get('packet_loss', 0)
        throughput = metrics.get('throughput', 0)
        
        new_resolution = self.current_resolution
        
        # Decision logic for resolution adaptation
        if (latency > self.thresholds['latency_high'] or 
            jitter > self.thresholds['jitter_high'] or 
            packet_loss > self.thresholds['packet_loss_high'] or
            throughput < self.thresholds['throughput_low']):
            
            # Network conditions are poor, decrease resolution
            if self.current_resolution == '4K':
                new_resolution = '1080p'
            elif self.current_resolution == '1080p':
                new_resolution = '720p'
            elif self.current_resolution == '720p':
                new_resolution = '480p'
            elif self.current_resolution == '480p':
                new_resolution = '360p'
            elif self.current_resolution == '360p':
                new_resolution = '240p'
            
        elif (latency < self.thresholds['latency_low'] and 
              jitter < self.thresholds['jitter_high'] / 2 and 
              packet_loss < self.thresholds['packet_loss_high'] / 2 and
              throughput > self.thresholds['throughput_high']):
            
            # Network conditions are good, increase resolution
            if self.current_resolution == '240p':
                new_resolution = '360p'
            elif self.current_resolution == '360p':
                new_resolution = '480p'
            elif self.current_resolution == '480p':
                new_resolution = '720p'
            elif self.current_resolution == '720p':
                new_resolution = '1080p'
            elif self.current_resolution == '1080p':
                new_resolution = '4K'
        
        if new_resolution != self.current_resolution:
            print(f"Resolution adaptation: {self.current_resolution} -> {new_resolution}")
            print(f"Metrics: Latency={latency:.1f}ms, Jitter={jitter:.1f}ms, "
                  f"Loss={packet_loss:.1f}%, Throughput={throughput:.0f}B/s")
            
            self.current_resolution = new_resolution
            self.last_adaptation_time = current_time
            self.resolution_history.append((current_time, new_resolution))
        
        return self.current_resolution

class VideoStreamingClient:
    def __init__(self, server_host='10.177.60.65', video_port=8890, control_port=8889):
        self.server_host = server_host
        self.video_port = video_port
        self.control_port = control_port
        
        # Components
        self.network_monitor = NetworkMonitor()
        self.adaptation_engine = ResolutionAdaptationEngine()
        
        # Sockets
        self.video_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.control_socket = None
        
        # State
        self.is_running = False
        self.current_resolution = '1080p'
        
        print(f"Client initialized for server {server_host}:{video_port}")
    
    def connect_to_server(self):
        """Establish connection to server"""
        try:
            # Bind video socket
            self.video_socket.bind(('', self.video_port))
            print(f"Video socket bound to port {self.video_port}")
            
            # Connect control socket
            self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.control_socket.connect((self.server_host, self.control_port))
            print(f"Connected to control server at {self.server_host}:{self.control_port}")
            
            return True
            
        except Exception as e:
            print(f"Error connecting to server: {e}")
            return False
    
    def send_resolution_request(self, resolution):
        """Send resolution change request to server"""
        if self.control_socket:
            try:
                message = {
                    'type': 'resolution_request',
                    'resolution': resolution,
                    'timestamp': time.time()
                }
                self.control_socket.send(json.dumps(message).encode())
                
                # Wait for acknowledgment
                response = self.control_socket.recv(1024).decode()
                ack = json.loads(response)
                if ack['type'] == 'resolution_ack':
                    print(f"Resolution change acknowledged: {ack['resolution']}")
                    return True
                    
            except Exception as e:
                print(f"Error sending resolution request: {e}")
        
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
            
            resolution_len = struct.unpack('!B', data[offset:offset+1])[0]
            offset += 1
            
            resolution = data[offset:offset+resolution_len].decode()
            offset += resolution_len
            
            data_len = struct.unpack('!I', data[offset:offset+4])[0]
            offset += 4
            
            # Extract frame data
            frame_data = data[offset:offset+data_len]
            
            return sequence_num, timestamp, resolution, frame_data
            
        except Exception as e:
            print(f"Error parsing packet: {e}")
            return None, None, None, None
    
    def start_streaming(self):
        """Start the video streaming client"""
        if not self.connect_to_server():
            return
        
        self.is_running = True
        
        # Start video receiving thread
        video_thread = threading.Thread(target=self.receive_video)
        video_thread.daemon = True
        video_thread.start()
        
        # Main loop for resolution adaptation
        try:
            print("\n🎥 Starting video streaming client...")
            print("📊 Monitoring network metrics and adapting resolution...")
            print("Press Ctrl+C to stop\n")
            
            while self.is_running:
                time.sleep(1.0)  # Check every second
                
                # Get current network metrics
                metrics = self.network_monitor.get_metrics()
                
                # Check if resolution should be adapted
                new_resolution = self.adaptation_engine.should_adapt_resolution(metrics)
                
                if new_resolution != self.current_resolution:
                    if self.send_resolution_request(new_resolution):
                        self.current_resolution = new_resolution
                        print(f"Resolution request sent to server for: {self.current_resolution}")
                
        except KeyboardInterrupt:
            print("\n🛑 Stopping client...")
        finally:
            self.cleanup()
    
    def receive_video(self):
        """Receive and display video frames"""
        print("📡 Starting video reception...")
        
        # Create OpenCV window at position 0,0
        cv2.namedWindow('Video Stream', cv2.WINDOW_NORMAL)  # Allow manual resizing
        cv2.resizeWindow('Video Stream', 1600, 900)  # Set to 900p size
        cv2.moveWindow('Video Stream', 0, 0)  # Position window at top-left corner
        
        while self.is_running:
            try:
                data, addr = self.video_socket.recvfrom(65536)  # Max UDP packet size
                
                # Parse packet
                seq_num, timestamp, resolution, frame_data = self.parse_packet(data)
                
                if frame_data is not None:
                    # Update network monitoring
                    self.network_monitor.add_packet(seq_num, timestamp, len(data))
                    
                    # Decode frame
                    frame = cv2.imdecode(np.frombuffer(frame_data, dtype=np.uint8), cv2.IMREAD_COLOR)
                    
                    if frame is not None:
                        # Always upscale to 1080p for display (regardless of received resolution)
                        display_frame = cv2.resize(frame, (1600, 900))
                        
                        # Add overlay with current metrics (pass the actual received resolution)
                        self.add_metrics_overlay(display_frame, resolution)
                        
                        # Display the 1080p frame
                        cv2.imshow('Video Stream', display_frame)
                        
                        # Check for quit command
                        key = cv2.waitKey(1) & 0xFF
                        if key == ord('q'):
                            print("User pressed 'q' - stopping client...")
                            self.is_running = False
                            break
                        elif key == ord('f'):
                            # Toggle fullscreen
                            cv2.setWindowProperty('Video Stream', cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
                        elif key == ord('w'):
                            # Return to windowed mode
                            cv2.setWindowProperty('Video Stream', cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_AUTOSIZE)
                
            except Exception as e:
                if self.is_running:
                    print(f"Error receiving video: {e}")
        
        cv2.destroyWindow('Video Stream')
    
    def add_metrics_overlay(self, frame, actual_resolution=None):
        """Add network metrics overlay to video frame"""
        metrics = self.network_monitor.get_metrics()
        
        # Get the actual stream quality from server (what server is sending)
        stream_quality = actual_resolution if actual_resolution else "unknown"
        
        # Get resolution dimensions for the stream quality
        resolution_map = {
            '240p': '426x240',
            '360p': '640x360',
            '480p': '854x480', 
            '720p': '1280x720',
            '1080p': '1920x1080',
            '4K': '3840x2160'
        }
        stream_resolution = resolution_map.get(stream_quality, 'unknown')
        
        # Add text overlay
        y_offset = 30
        
        # 1. Display Resolution (static - client window size)
        cv2.putText(frame, f"Display Resolution: 1600x900", 
                   (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        y_offset += 30
        
        # 2. Stream Quality (dynamic - what server is actually sending)
        cv2.putText(frame, f"Stream Quality: {stream_quality}({stream_resolution})", 
                   (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
        y_offset += 35
        
        # Other metrics (smaller text)
        cv2.putText(frame, f"Latency: {metrics['latency']:.1f}ms", 
                   (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        y_offset += 20
        
        cv2.putText(frame, f"Jitter: {metrics['jitter']:.1f}ms", 
                   (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        y_offset += 20
        
        cv2.putText(frame, f"Loss: {metrics['packet_loss']:.1f}%", 
                   (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        y_offset += 20
        
        cv2.putText(frame, f"Throughput: {metrics['throughput']/1000:.1f} KB/s", 
                   (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
    
    def cleanup(self):
        """Clean up resources"""
        self.is_running = False
        
        if self.video_socket:
            self.video_socket.close()
        
        if self.control_socket:
            self.control_socket.close()
        
        cv2.destroyAllWindows()
        
        print("🧹 Client cleanup completed")

def main():
    client = VideoStreamingClient()
    try:
        client.start_streaming()
    except KeyboardInterrupt:
        print("\nShutting down client...")
    finally:
        client.cleanup()

if __name__ == "__main__":
    main()