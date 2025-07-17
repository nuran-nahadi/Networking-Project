import socket
import threading
import time
import cv2
import json
import struct
import numpy as np
from collections import deque
import statistics
from config import INITIAL_RESOLUTION, SERVER_IP, CLIENT_IP

class ChunkNetworkMonitor:
    def __init__(self, window_size=100, throughput_window_seconds=1.0):
        self.window_size = window_size
        self.throughput_window_seconds = throughput_window_seconds
        self.packet_times = deque(maxlen=window_size)
        self.packet_sizes = deque(maxlen=window_size)
        self.sequence_numbers = deque(maxlen=window_size)
        self.latencies = deque(maxlen=window_size)
        self.chunk_info = deque(maxlen=window_size)  # Track chunk transitions
        
        # Network metrics
        self.packet_loss_rate = 0.0
        self.jitter = 0.0
        self.average_latency = 0.0
        self.throughput = 0.0
        self.chunk_switch_rate = 0.0  # Chunks per second
        
        self.last_sequence = -1
        self.lost_packets = 0
        self.total_packets = 0
        self.last_chunk_id = -1
        self.chunk_switches = 0
        
    def add_packet(self, sequence_num, timestamp, packet_size, chunk_id, frame_index):
        """Add packet information for analysis"""
        current_time = time.time()
        
        # Calculate latency
        latency = (current_time - timestamp) * 1000  # Convert to milliseconds
        
        self.packet_times.append(current_time)
        self.packet_sizes.append(packet_size)
        self.sequence_numbers.append(sequence_num)
        self.latencies.append(latency)
        self.chunk_info.append((chunk_id, frame_index))
        
        # Track chunk switches
        if chunk_id != self.last_chunk_id:
            self.chunk_switches += 1
            self.last_chunk_id = chunk_id
        
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
        
        # Calculate throughput using sliding time window
        if len(self.packet_times) >= 2:
            current_time = self.packet_times[-1]
            cutoff_time = current_time - self.throughput_window_seconds
            
            bytes_in_window = 0
            packets_in_window = 0
            
            for i in range(len(self.packet_times) - 1, -1, -1):
                if self.packet_times[i] >= cutoff_time:
                    bytes_in_window += self.packet_sizes[i]
                    packets_in_window += 1
                else:
                    break
            
            if packets_in_window > 1:
                time_span = self.packet_times[-1] - self.packet_times[-packets_in_window]
                if time_span > 0:
                    self.throughput = bytes_in_window / max(time_span, self.throughput_window_seconds)
                else:
                    self.throughput = bytes_in_window / self.throughput_window_seconds
            else:
                self.throughput = 0.0
    
    def get_metrics(self):
        """Return current network metrics"""
        return {
            'latency': self.average_latency,
            'jitter': self.jitter,
            'packet_loss': self.packet_loss_rate,
            'throughput': self.throughput,
            'chunk_switches': self.chunk_switches
        }

class ChunkResolutionEngine:
    def __init__(self):
        self.current_resolution = INITIAL_RESOLUTION
        self.resolution_history = deque(maxlen=50)
        
        # Base thresholds for chunk-based streaming
        self.base_thresholds = {
            'latency_high': 200,       # ms
            'latency_low': 100,        # ms
            'jitter_high': 50,         # ms
            'packet_loss_high': 10,   # %
        }
        
        # Adaptive throughput thresholds based on resolution (in bytes/sec)
        self.resolution_throughput_thresholds = {
            '240p': {
                'throughput_low': 80000,    # 80 KB/s (640 kbps) - minimum for 240p
                'throughput_high': 150000   # 150 KB/s (1.2 Mbps) - upgrade to 360p
            },
            '360p': {
                'throughput_low': 120000,   # 120 KB/s (960 kbps) - minimum for 360p  
                'throughput_high': 250000   # 250 KB/s (2 Mbps) - upgrade to 480p
            },
            '480p': {
                'throughput_low': 200000,   # 200 KB/s (1.6 Mbps) - minimum for 480p
                'throughput_high': 400000   # 400 KB/s (3.2 Mbps) - upgrade to 720p
            },
            '720p': {
                'throughput_low': 350000,   # 350 KB/s (2.8 Mbps) - minimum for 720p
                'throughput_high': 750000   # 750 KB/s (6 Mbps) - upgrade to 1080p
            },
            '1080p': {
                'throughput_low': 600000,   # 600 KB/s (4.8 Mbps) - minimum for 1080p
                'throughput_high': 1500000  # 1.5 MB/s (12 Mbps) - maintain 1080p
            }
        }
        
        self.last_adaptation_time = 0
        self.adaptation_cooldown = 7.0  # seconds
        self.last_trigger = "None"  # Track what triggered the last resolution change
    
    def should_adapt_resolution(self, metrics):
        """Determine if resolution should be changed for chunk streaming with adaptive thresholds"""
        current_time = time.time()
        
        # Prevent too frequent adaptations
        if current_time - self.last_adaptation_time < self.adaptation_cooldown:
            return self.current_resolution
        
        latency = metrics.get('latency', 0)
        jitter = metrics.get('jitter', 0)
        packet_loss = metrics.get('packet_loss', 0)
        throughput = metrics.get('throughput', 0)
        
        # Get adaptive thresholds for current resolution
        current_thresholds = self.resolution_throughput_thresholds.get(
            self.current_resolution, 
            self.resolution_throughput_thresholds[INITIAL_RESOLUTION]  # fallback
        )
        
        new_resolution = self.current_resolution
        trigger_reason = "None"
        
        # Check individual conditions and track which one triggers the change
        latency_poor = latency > self.base_thresholds['latency_high']
        jitter_poor = jitter > self.base_thresholds['jitter_high']
        packet_loss_poor = packet_loss > self.base_thresholds['packet_loss_high']
        throughput_poor = throughput < current_thresholds['throughput_low']
        
        latency_good = latency < self.base_thresholds['latency_low']
        jitter_good = jitter < self.base_thresholds['jitter_high'] / 2
        packet_loss_good = packet_loss < self.base_thresholds['packet_loss_high'] / 2
        throughput_good = throughput > current_thresholds['throughput_high']
        
        # Decision logic for resolution adaptation with trigger tracking
        poor_network_conditions = latency_poor or jitter_poor or packet_loss_poor or throughput_poor
        good_network_conditions = latency_good and jitter_good and packet_loss_good and throughput_good
        
        if poor_network_conditions:
            # Determine which metric triggered the downgrade
            if latency_poor:
                trigger_reason = "High Latency"
            elif jitter_poor:
                trigger_reason = "High Jitter"
            elif packet_loss_poor:
                trigger_reason = "Packet Loss"
            elif throughput_poor:
                trigger_reason = "Low Throughput"
            
            # Network conditions are poor, decrease resolution
            if self.current_resolution == '1080p':
                new_resolution = '720p'
            elif self.current_resolution == '720p':
                new_resolution = '480p'
            elif self.current_resolution == '480p':
                new_resolution = '360p'
            elif self.current_resolution == '360p':
                new_resolution = '240p'
            
        elif good_network_conditions:
            trigger_reason = "Good Network"
            
            # Network conditions are good, increase resolution
            if self.current_resolution == '240p':
                new_resolution = '360p'
            elif self.current_resolution == '360p':
                new_resolution = '480p'
            elif self.current_resolution == '480p':
                new_resolution = '720p'
            elif self.current_resolution == '720p':
                new_resolution = '1080p'
        
        if new_resolution != self.current_resolution:
            old_thresholds = current_thresholds
            new_thresholds = self.resolution_throughput_thresholds.get(new_resolution, {})
            
            print(f"🎯 Adaptive resolution change: {self.current_resolution} → {new_resolution}")
            print(f"📊 Current Metrics: Latency={latency:.1f}ms, Jitter={jitter:.1f}ms, "
                  f"Loss={packet_loss:.1f}%, Throughput={throughput/1000:.1f}KB/s")
            print(f"🔧 Old thresholds: Low={old_thresholds['throughput_low']/1000:.0f}KB/s, "
                  f"High={old_thresholds['throughput_high']/1000:.0f}KB/s")
            print(f"🔧 New thresholds: Low={new_thresholds.get('throughput_low', 0)/1000:.0f}KB/s, "
                  f"High={new_thresholds.get('throughput_high', 0)/1000:.0f}KB/s")
            
            # Store the trigger reason
            self.last_trigger = trigger_reason
            
            # Print colored trigger feedback
            if trigger_reason == "Good Network":
                print(f"🟢 Trigger: {trigger_reason}")
            else:
                print(f"🔴 Trigger: {trigger_reason}")
            
            self.current_resolution = new_resolution
            self.last_adaptation_time = current_time
            self.resolution_history.append((current_time, new_resolution))
        
        return self.current_resolution
    
    def get_current_thresholds(self):
        """Get the current adaptive thresholds for the active resolution"""
        return self.resolution_throughput_thresholds.get(
            self.current_resolution, 
            self.resolution_throughput_thresholds[INITIAL_RESOLUTION]  # fallback
        )
    
    def get_last_trigger(self):
        """Get the last trigger reason for resolution change"""
        return self.last_trigger

class ChunkBasedClient:
    def __init__(self, server_host=SERVER_IP, video_port=8890, control_port=8889):
        self.server_host = server_host
        self.video_port = video_port
        self.control_port = control_port
        
        # Components
        self.network_monitor = ChunkNetworkMonitor()
        self.adaptation_engine = ChunkResolutionEngine()
        
        # Sockets
        self.video_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.control_socket = None
        
        # State
        self.is_running = False
        self.current_resolution = INITIAL_RESOLUTION
        self.current_chunk = 0
        self.total_chunks = 0
        self.chunk_duration = 2.0  # Updated to match server's 2-second chunks
        
        # Chunk tracking
        self.received_frames = {}  # {chunk_id: [frames]}
        self.chunk_complete = set()  # Set of completed chunk IDs
        self.frame_fragments = {}  # {(chunk_id, frame_index): {fragment_index: data}}
        self.frame_fragment_counts = {}  # {(chunk_id, frame_index): total_fragments}
        
        print(f"🎬 Chunk-based client initialized for server {server_host}:{video_port}")
        print(f"🌐 Client IP configured as: {CLIENT_IP}")
    
    def connect_to_server(self):
        """Establish connection to server"""
        try:
            # Bind video socket to specific IP if configured
            self.video_socket.bind((CLIENT_IP, self.video_port))
            print(f"📡 Video socket bound to {CLIENT_IP}:{self.video_port}")
            
            # Connect control socket
            self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.control_socket.connect((self.server_host, self.control_port))
            print(f"🔗 Connected to control server at {self.server_host}:{self.control_port}")
            
            # Wait for registration acknowledgment
            response = self.control_socket.recv(1024).decode()
            ack = json.loads(response)
            if ack['type'] == 'registration_ack' and ack['status'] == 'success':
                self.total_chunks = ack['total_chunks']
                self.chunk_duration = ack['chunk_duration']
                print(f"✅ Registered! Total chunks: {self.total_chunks}, Duration: {self.chunk_duration}s each")
                return True
            
            return False
            
        except Exception as e:
            print(f"❌ Error connecting to server: {e}")
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
                    print(f"🎯 Resolution change acknowledged: {ack['resolution']}")
                    return True
                    
            except Exception as e:
                print(f"❌ Error sending resolution request: {e}")
        
        return False
    
    def send_chunk_request(self, chunk_id):
        """Request specific chunk from server"""
        if self.control_socket:
            try:
                message = {
                    'type': 'chunk_request',
                    'chunk_id': chunk_id,
                    'timestamp': time.time()
                }
                self.control_socket.send(json.dumps(message).encode())
                return True
            except Exception as e:
                print(f"❌ Error sending chunk request: {e}")
        return False
    
    def reassemble_frame(self, chunk_id, frame_index, fragment_data, total_fragments, fragment_index):
        """Reassemble fragmented frame data"""
        frame_key = (chunk_id, frame_index)
        
        # Initialize fragment storage for this frame
        if frame_key not in self.frame_fragments:
            self.frame_fragments[frame_key] = {}
            self.frame_fragment_counts[frame_key] = total_fragments
        
        # Store fragment
        self.frame_fragments[frame_key][fragment_index] = fragment_data
        
        # Check if frame is complete
        if len(self.frame_fragments[frame_key]) == total_fragments:
            # Reassemble frame by concatenating fragments in order
            complete_frame_data = b''
            for i in range(total_fragments):
                if i in self.frame_fragments[frame_key]:
                    complete_frame_data += self.frame_fragments[frame_key][i]
                else:
                    # Missing fragment, frame incomplete
                    return None
            
            # Clean up fragment storage
            del self.frame_fragments[frame_key]
            del self.frame_fragment_counts[frame_key]
            
            return complete_frame_data
        
        return None  # Frame not yet complete
    
    def parse_chunk_packet(self, data):
        """Parse incoming chunk packet with fragmentation support"""
        try:
            offset = 0
            
            # Parse header
            sequence_num = struct.unpack('!I', data[offset:offset+4])[0]
            offset += 4
            
            timestamp = struct.unpack('!d', data[offset:offset+8])[0]
            offset += 8
            
            chunk_id = struct.unpack('!I', data[offset:offset+4])[0]
            offset += 4
            
            frame_index = struct.unpack('!I', data[offset:offset+4])[0]
            offset += 4
            
            resolution_len = struct.unpack('!B', data[offset:offset+1])[0]
            offset += 1
            
            resolution = data[offset:offset+resolution_len].decode()
            offset += resolution_len
            
            total_fragments = struct.unpack('!I', data[offset:offset+4])[0]
            offset += 4
            
            fragment_index = struct.unpack('!I', data[offset:offset+4])[0]
            offset += 4
            
            fragment_size = struct.unpack('!I', data[offset:offset+4])[0]
            offset += 4
            
            # Extract fragment data
            fragment_data = data[offset:offset+fragment_size]
            
            return sequence_num, timestamp, chunk_id, frame_index, resolution, fragment_data, total_fragments, fragment_index
            
        except Exception as e:
            print(f"❌ Error parsing chunk packet: {e}")
            return None, None, None, None, None, None, None, None
    
    def handle_terminal_input(self):
        """Handle terminal input for manual control"""
        available_resolutions = ['240p', '360p', '480p', '720p', '1080p']
        
        print("\n🎮 Manual Control Commands:")
        print("  - Type resolution: 240p, 360p, 480p, 720p, 1080p")
        print("  - Type 'chunk X' to jump to chunk X")
        print("  - Type 'status' for current metrics")
        print("  - Type 'help' for this help")
        print("  - Type 'quit' to stop")
        
        while self.is_running:
            try:
                # Python 3 compatible input
                command = input("🎮 > ").strip().lower()
                
                if command == 'quit' or command == 'q':
                    print("🛑 Stopping client...")
                    self.is_running = False
                    break
                elif command == 'help':
                    print(f"📋 Available resolutions: {', '.join(available_resolutions)}")
                    print("📦 Commands: chunk X, status, help, quit")
                elif command == 'status':
                    metrics = self.network_monitor.get_metrics()
                    current_thresholds = self.adaptation_engine.get_current_thresholds()
                    print(f"📊 Current Status:")
                    print(f"   Resolution: {self.current_resolution}")
                    print(f"   Current Chunk: {self.current_chunk}/{self.total_chunks}")
                    print(f"   Latency: {metrics['latency']:.1f}ms")
                    print(f"   Jitter: {metrics['jitter']:.1f}ms")
                    print(f"   Loss: {metrics['packet_loss']:.1f}%")
                    print(f"   Throughput: {metrics['throughput']/1000:.1f} KB/s")
                    print(f"   Chunk Switches: {metrics['chunk_switches']}")
                    print(f"🎯 Adaptive Thresholds for {self.current_resolution}:")
                    print(f"   Min Throughput: {current_thresholds['throughput_low']/1000:.0f} KB/s")
                    print(f"   Upgrade Threshold: {current_thresholds['throughput_high']/1000:.0f} KB/s")
                elif command.startswith('chunk '):
                    try:
                        chunk_num = int(command.split()[1])
                        if 0 <= chunk_num < self.total_chunks:
                            print(f"📦 Requesting jump to chunk {chunk_num}")
                            self.send_chunk_request(chunk_num)
                        else:
                            print(f"❌ Invalid chunk number. Range: 0-{self.total_chunks-1}")
                    except ValueError:
                        print("❌ Invalid chunk number format")
                elif command in [r.lower() for r in available_resolutions]:
                    resolution = next(r for r in available_resolutions if r.lower() == command)
                    print(f"🎯 Requesting resolution change to {resolution}...")
                    if self.send_resolution_request(resolution):
                        self.current_resolution = resolution
                elif command == '':
                    continue
                else:
                    print(f"❌ Unknown command: {command}")
                    print("💡 Type 'help' for available commands")
                    
            except (EOFError, KeyboardInterrupt):
                break
            except Exception as e:
                print(f"❌ Input error: {e}")
            
            time.sleep(0.1)
    
    def start_streaming(self):
        """Start the chunk-based streaming client"""
        if not self.connect_to_server():
            return
        
        self.is_running = True
        
        # Start video receiving thread
        video_thread = threading.Thread(target=self.receive_chunks)
        video_thread.daemon = True
        video_thread.start()
        
        # Start terminal input handler
        input_thread = threading.Thread(target=self.handle_terminal_input)
        input_thread.daemon = True
        input_thread.start()
        
        # Main loop for adaptive streaming
        try:
            print("\n🎬 Starting chunk-based streaming client...")
            print("📊 Monitoring network metrics and adapting resolution...")
            print("💬 Terminal input available for manual control")
            print("Press Ctrl+C to stop\n")
            
            while self.is_running:
                time.sleep(1.0)
                
                # Get current network metrics
                metrics = self.network_monitor.get_metrics()
                
                # Check if resolution should be adapted
                new_resolution = self.adaptation_engine.should_adapt_resolution(metrics)
                
                if new_resolution != self.current_resolution:
                    print(f"🔄 Auto-adapting resolution: {self.current_resolution} → {new_resolution}")
                    if self.send_resolution_request(new_resolution):
                        self.current_resolution = new_resolution
                
        except KeyboardInterrupt:
            print("\n🛑 Stopping client...")
        finally:
            self.cleanup()
    
    def receive_chunks(self):
        """Receive and display chunk-based video"""
        print("📡 Starting chunk reception...")
        
        # Create OpenCV window
        cv2.namedWindow('Chunk Video Stream', cv2.WINDOW_NORMAL)
        cv2.resizeWindow('Chunk Video Stream', 1600, 900)
        cv2.moveWindow('Chunk Video Stream', 0, 0)
        
        frame_count = 0
        
        while self.is_running:
            try:
                data, addr = self.video_socket.recvfrom(65536)
                
                # Parse chunk packet (now with fragmentation support)
                result = self.parse_chunk_packet(data)
                if len(result) == 8:  # Fragmented packet
                    seq_num, timestamp, chunk_id, frame_index, resolution, fragment_data, total_fragments, fragment_index = result
                    
                    if fragment_data is not None:
                        # Update network monitoring with fragment info
                        self.network_monitor.add_packet(seq_num, timestamp, len(data), chunk_id, frame_index)
                        
                        # Try to reassemble the complete frame
                        complete_frame_data = self.reassemble_frame(
                            chunk_id, frame_index, fragment_data, total_fragments, fragment_index
                        )
                        
                        if complete_frame_data is not None:
                            # Frame is complete, process it
                            frame_count += 1
                            
                            # Store frame in chunk buffer
                            if chunk_id not in self.received_frames:
                                self.received_frames[chunk_id] = {}
                            
                            self.received_frames[chunk_id][frame_index] = complete_frame_data
                            self.current_chunk = chunk_id
                            
                            # Decode and display frame
                            frame = cv2.imdecode(np.frombuffer(complete_frame_data, dtype=np.uint8), cv2.IMREAD_COLOR)
                            
                            if frame is not None:
                                # Always upscale to display size
                                display_frame = cv2.resize(frame, (1600, 900))
                                
                                # Add overlay with chunk information
                                self.add_chunk_overlay(display_frame, resolution, chunk_id, frame_index)
                                
                                # Display frame
                                cv2.imshow('Chunk Video Stream', display_frame)
                                
                                # Handle keyboard input
                                key = cv2.waitKey(1) & 0xFF
                                if key == ord('q'):
                                    print("🛑 User pressed 'q' - stopping client...")
                                    self.is_running = False
                                    break
                                elif key == ord('f'):
                                    cv2.setWindowProperty('Chunk Video Stream', cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
                                elif key == ord('w'):
                                    cv2.setWindowProperty('Chunk Video Stream', cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_AUTOSIZE)
                
            except Exception as e:
                if self.is_running:
                    print(f"❌ Error receiving video: {e}")
        
        cv2.destroyWindow('Chunk Video Stream')
    
    def add_chunk_overlay(self, frame, resolution, chunk_id, frame_index):
        """Add chunk information overlay to video frame"""
        metrics = self.network_monitor.get_metrics()
        current_thresholds = self.adaptation_engine.get_current_thresholds()
        
        # Resolution dimensions
        resolution_map = {
            '240p': '426x240',
            '360p': '640x360',
            '480p': '854x480',
            '720p': '1280x720',
            '1080p': '1920x1080'
        }
        stream_resolution = resolution_map.get(resolution, 'unknown')
        
        y_offset = 30
        
        # Display resolution
        cv2.putText(frame, f"Display Resolution: 1600x900", 
                   (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
        y_offset += 30
        
        # Stream quality
        cv2.putText(frame, f"Stream Quality: {resolution}({stream_resolution})", 
                   (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 0), 2)
        y_offset += 30
        
        # Chunk information
        cv2.putText(frame, f"Chunk: {chunk_id}/{self.total_chunks} | Frame: {frame_index}", 
                   (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
        y_offset += 30
        
        # Mode indicator
        cv2.putText(frame, "Mode: CHUNK-BASED (Adaptive)", 
                   (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 0, 255), 2)
        y_offset += 30
        
        # Network information
        cv2.putText(frame, f"Server: {SERVER_IP} | Client: {CLIENT_IP}", 
                   (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        y_offset += 25
        
        # Chunk duration indicator
        cv2.putText(frame, f"Chunk Duration: {self.chunk_duration}s", 
                   (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 255), 1)
        y_offset += 25
        
        # Network metrics
        cv2.putText(frame, f"Latency: {metrics['latency']:.1f}ms", 
                   (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        y_offset += 20
        
        cv2.putText(frame, f"Jitter: {metrics['jitter']:.1f}ms", 
                   (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        y_offset += 20
        
        cv2.putText(frame, f"Loss: {metrics['packet_loss']:.1f}%", 
                   (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
        y_offset += 20
        
        # Throughput with adaptive thresholds
        throughput_kb = metrics['throughput']/1000
        min_threshold_kb = current_thresholds['throughput_low']/1000
        upgrade_threshold_kb = current_thresholds['throughput_high']/1000
        
        # Color code throughput based on thresholds
        if throughput_kb < min_threshold_kb:
            throughput_color = (0, 0, 255)  # Red - below minimum
        elif throughput_kb > upgrade_threshold_kb:
            throughput_color = (0, 255, 0)  # Green - above upgrade threshold
        else:
            throughput_color = (0, 255, 255)  # Yellow - in acceptable range
        
        cv2.putText(frame, f"Throughput: {throughput_kb:.1f} KB/s", 
                   (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, throughput_color, 1)
        y_offset += 20
        
        # Show trigger information with color coding
        last_trigger = self.adaptation_engine.get_last_trigger()
        
        # Color code trigger based on whether it's upgrade (green) or downgrade (red)
        if last_trigger == "Good Network":
            trigger_color = (0, 255, 0)  # Green - resolution upgraded
        elif last_trigger == "None":
            trigger_color = (255, 255, 255)  # White - no changes yet
        else:
            trigger_color = (0, 0, 255)  # Red - resolution downgraded due to poor conditions
        
        cv2.putText(frame, f"Trigger: {last_trigger}", 
                   (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.5, trigger_color, 1)
        y_offset += 20
        
        # Show adaptive thresholds
        cv2.putText(frame, f"Thresholds: Min={min_threshold_kb:.0f} | Up={upgrade_threshold_kb:.0f} KB/s", 
                   (10, y_offset), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (200, 200, 200), 1)
    
    def cleanup(self):
        """Clean up resources"""
        self.is_running = False
        
        if self.video_socket:
            self.video_socket.close()
        
        if self.control_socket:
            self.control_socket.close()
        
        cv2.destroyAllWindows()
        
        print("🧹 Chunk client cleanup completed")

def main():
    print(f"🌐 Connecting to server: {SERVER_IP}")
    print(f"🖥️  Client IP configured as: {CLIENT_IP}")
    
    client = ChunkBasedClient()
    try:
        client.start_streaming()
    except KeyboardInterrupt:
        print("\n👋 Shutting down client...")
    finally:
        client.cleanup()

if __name__ == "__main__":
    main()