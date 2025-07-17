import socket
import threading
import time
import cv2
import json
import struct
import os
import shutil
from typing import Dict, List, Tuple
import numpy as np
from config import INITIAL_RESOLUTION, SERVER_IP

class ChunkBasedVideoServer:
    def __init__(self, host=SERVER_IP, video_port=8888, control_port=8889, video_file_path=None):
        self.host = host
        self.video_port = video_port
        self.control_port = control_port
        self.video_file_path = video_file_path
        
        # Video settings for different resolutions
        self.resolutions = {
            '240p': (426, 240, 60),      # width, height, quality
            '360p': (640, 360, 65),
            '480p': (854, 480, 70),
            '720p': (1280, 720, 75),
            '1080p': (1920, 1080, 85)
        }
        
        # Chunk settings
        self.chunk_duration = 2.0  # seconds per chunk (smaller chunks for better control)
        self.chunks_storage = {}   # {resolution: [chunk_files]}
        self.chunk_metadata = {}   # {chunk_id: {duration, frame_count, etc}}
        self.total_chunks = 0
        self.original_fps = 30
        
        # Client tracking
        self.clients = {}  # {addr: {resolution, current_chunk}}
        self.is_streaming = False
        
        # Socket setup
        self.video_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.control_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        print(f"Chunk-based server initialized on {host}:{video_port} (video) and {control_port} (control)")
    
    def preprocess_video(self):
        """Pre-process video into chunks at different resolutions"""
        if not self.video_file_path or not os.path.exists(self.video_file_path):
            print("Error: No valid video file provided")
            return False
        
        print(f"📁 Pre-processing video: {os.path.basename(self.video_file_path)}")
        print(f"⏱️  Using 2-second chunks for better streaming control")
        
        # Create storage directory
        storage_dir = "video_chunks"
        if os.path.exists(storage_dir):
            shutil.rmtree(storage_dir)
        os.makedirs(storage_dir)
        
        # Open video file
        cap = cv2.VideoCapture(self.video_file_path)
        if not cap.isOpened():
            print("Error: Could not open video file")
            return False
        
        # Get video properties
        self.original_fps = cap.get(cv2.CAP_PROP_FPS)
        total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        duration = total_frames / self.original_fps
        
        print(f"  Original FPS: {self.original_fps:.2f}")
        print(f"  Total frames: {total_frames}")
        print(f"  Duration: {duration:.2f} seconds")
        
        # Calculate chunk parameters
        frames_per_chunk = int(self.original_fps * self.chunk_duration)
        self.total_chunks = int(np.ceil(total_frames / frames_per_chunk))
        
        print(f"  Frames per chunk: {frames_per_chunk}")
        print(f"  Total chunks: {self.total_chunks}")
        print()
        
        # Initialize storage for each resolution
        for resolution in self.resolutions.keys():
            self.chunks_storage[resolution] = []
            res_dir = os.path.join(storage_dir, resolution)
            os.makedirs(res_dir)
        
        # Process chunks
        for chunk_id in range(self.total_chunks):
            print(f"🔄 Processing chunk {chunk_id + 1}/{self.total_chunks}")
            
            # Read frames for this chunk
            chunk_frames = []
            for frame_idx in range(frames_per_chunk):
                ret, frame = cap.read()
                if not ret:
                    break
                chunk_frames.append(frame)
            
            if not chunk_frames:
                break
            
            # Store metadata
            self.chunk_metadata[chunk_id] = {
                'frame_count': len(chunk_frames),
                'duration': len(chunk_frames) / self.original_fps
            }
            
            # Process chunk for each resolution
            for resolution, (width, height, quality) in self.resolutions.items():
                chunk_file = os.path.join(storage_dir, resolution, f"chunk_{chunk_id:04d}.bin")
                
                # Resize and encode frames
                encoded_frames = []
                for frame in chunk_frames:
                    # Resize frame
                    resized_frame = cv2.resize(frame, (width, height))
                    
                    # Encode frame as JPEG
                    encode_params = [cv2.IMWRITE_JPEG_QUALITY, quality]
                    _, buffer = cv2.imencode('.jpg', resized_frame, encode_params)
                    encoded_frames.append(buffer.tobytes())
                
                # Save chunk to file
                with open(chunk_file, 'wb') as f:
                    # Write number of frames
                    f.write(struct.pack('!I', len(encoded_frames)))
                    
                    # Write each frame with its size
                    for frame_data in encoded_frames:
                        f.write(struct.pack('!I', len(frame_data)))
                        f.write(frame_data)
                
                self.chunks_storage[resolution].append(chunk_file)
        
        cap.release()
        print(f"✅ Video preprocessing complete! Created {self.total_chunks} chunks for {len(self.resolutions)} resolutions")
        return True
    
    def load_chunk(self, resolution, chunk_id):
        """Load a specific chunk from storage"""
        if resolution not in self.chunks_storage or chunk_id >= len(self.chunks_storage[resolution]):
            return None
        
        chunk_file = self.chunks_storage[resolution][chunk_id]
        if not os.path.exists(chunk_file):
            return None
        
        frames = []
        try:
            with open(chunk_file, 'rb') as f:
                # Read number of frames
                frame_count = struct.unpack('!I', f.read(4))[0]
                
                # Read each frame
                for _ in range(frame_count):
                    frame_size = struct.unpack('!I', f.read(4))[0]
                    frame_data = f.read(frame_size)
                    frames.append(frame_data)
            
            return frames
        except Exception as e:
            print(f"Error loading chunk {chunk_id} for {resolution}: {e}")
            return None
    
    def start_server(self):
        """Start the chunk-based streaming server"""
        # Pre-process video into chunks
        if not self.preprocess_video():
            return
        
        try:
            # Bind control socket
            self.control_socket.bind((self.host, self.control_port))
            self.control_socket.listen(5)
            print(f"🎮 Control server listening on {self.host}:{self.control_port}")
            
            self.is_streaming = True
            
            # Start control message handler
            control_thread = threading.Thread(target=self.handle_control_connections)
            control_thread.daemon = True
            control_thread.start()
            
            # Start chunk streaming
            self.stream_chunks()
            
        except Exception as e:
            print(f"Error starting server: {e}")
    
    def handle_control_connections(self):
        """Handle incoming control connections"""
        while self.is_streaming:
            try:
                client_socket, addr = self.control_socket.accept()
                print(f"🔗 Control connection from {addr}")
                
                # Handle client in separate thread
                client_thread = threading.Thread(target=self.handle_client_control, args=(client_socket, addr))
                client_thread.daemon = True
                client_thread.start()
                
            except Exception as e:
                if self.is_streaming:
                    print(f"Error accepting control connection: {e}")
    
    def handle_client_control(self, client_socket, addr):
        """Handle control messages from a specific client"""
        try:
            # Register client with default settings
            self.clients[addr] = {
                'resolution': INITIAL_RESOLUTION,
                'current_chunk': 0,
                'socket': client_socket
            }
            
            print(f"📱 Client {addr} registered with default resolution: {INITIAL_RESOLUTION}")
            
            # Send registration acknowledgment
            ack = {
                'type': 'registration_ack',
                'status': 'success',
                'total_chunks': self.total_chunks,
                'chunk_duration': self.chunk_duration
            }
            client_socket.send(json.dumps(ack).encode())
            
            # Handle control messages
            while self.is_streaming and addr in self.clients:
                try:
                    data = client_socket.recv(1024)
                    if not data:
                        break
                        
                    message = json.loads(data.decode())
                    
                    if message['type'] == 'resolution_request':
                        new_resolution = message['resolution']
                        if new_resolution in self.resolutions:
                            self.clients[addr]['resolution'] = new_resolution
                            print(f"🎯 Client {addr} changed resolution to {new_resolution}")
                            
                            # Send acknowledgment
                            ack = {
                                'type': 'resolution_ack',
                                'resolution': new_resolution,
                                'status': 'success'
                            }
                            client_socket.send(json.dumps(ack).encode())
                    
                    elif message['type'] == 'chunk_request':
                        chunk_id = message['chunk_id']
                        if 0 <= chunk_id < self.total_chunks:
                            self.clients[addr]['current_chunk'] = chunk_id
                            print(f"📦 Client {addr} requested chunk {chunk_id}")
                            
                except Exception as e:
                    print(f"Error handling control message from {addr}: {e}")
                    break
        
        except Exception as e:
            print(f"Error in client control handler for {addr}: {e}")
        finally:
            if addr in self.clients:
                del self.clients[addr]
            client_socket.close()
            print(f"🔌 Client {addr} disconnected")
    
    def create_chunk_packets(self, chunk_id, frame_index, resolution, frame_data, sequence_number):
        """Create packets for chunk-based streaming with fragmentation support"""
        max_packet_size = 60000  # Safe UDP packet size for Windows
        resolution_bytes = resolution.encode()
        
        # Calculate header size
        base_header_size = 4 + 8 + 4 + 4 + 1 + len(resolution_bytes) + 4 + 4 + 4  # Added fragment info
        max_payload_size = max_packet_size - base_header_size
        
        # Create packets with fragmentation
        packets = []
        total_fragments = (len(frame_data) + max_payload_size - 1) // max_payload_size
        
        for fragment_index in range(total_fragments):
            start_pos = fragment_index * max_payload_size
            end_pos = min(start_pos + max_payload_size, len(frame_data))
            fragment_data = frame_data[start_pos:end_pos]
            
            # Create header with fragmentation info:
            # sequence(4) + timestamp(8) + chunk_id(4) + frame_index(4) + resolution_len(1) + resolution + 
            # total_fragments(4) + fragment_index(4) + fragment_size(4) + fragment_data
            header = struct.pack('!I', sequence_number + fragment_index)  # unique sequence per fragment
            header += struct.pack('!d', time.time())                     # timestamp
            header += struct.pack('!I', chunk_id)                       # chunk ID
            header += struct.pack('!I', frame_index)                    # frame index within chunk
            header += struct.pack('!B', len(resolution_bytes))          # resolution string length
            header += resolution_bytes                                   # resolution string
            header += struct.pack('!I', total_fragments)                # total fragments for this frame
            header += struct.pack('!I', fragment_index)                 # current fragment index
            header += struct.pack('!I', len(fragment_data))             # fragment size
            
            packet = header + fragment_data
            packets.append(packet)
        
        return packets
    
    def stream_chunks(self):
        """Stream chunks to connected clients with improved chunk handling"""
        print("📡 Starting chunk streaming...")
        sequence_number = 0
        frame_rate = 30  # Target FPS
        frame_duration = 1.0 / frame_rate
        
        while self.is_streaming:
            start_time = time.time()
            
            try:
                # Send frames to all connected clients
                for addr, client_info in list(self.clients.items()):
                    resolution = client_info['resolution']
                    chunk_id = client_info['current_chunk']
                    
                    # Load chunk frames
                    frames = self.load_chunk(resolution, chunk_id)
                    if frames:
                        for frame_index, frame_data in enumerate(frames):
                            if not self.is_streaming:
                                break
                            
                            # Create packets for this frame
                            packets = self.create_chunk_packets(
                                chunk_id, frame_index, resolution, frame_data, sequence_number
                            )
                            
                            # Send all packets for this frame
                            for packet in packets:
                                try:
                                    self.video_socket.sendto(packet, (addr[0], self.video_port))
                                except Exception as e:
                                    print(f"Error sending packet to {addr}: {e}")
                            
                            sequence_number += len(packets)
                            
                            # Frame timing
                            time.sleep(frame_duration)
                        
                        # Auto-advance to next chunk
                        if chunk_id + 1 < self.total_chunks:
                            self.clients[addr]['current_chunk'] = chunk_id + 1
                        else:
                            # Loop back to beginning
                            self.clients[addr]['current_chunk'] = 0
                
                # Maintain loop timing
                elapsed = time.time() - start_time
                if elapsed < 0.1:  # Minimum loop delay
                    time.sleep(0.1 - elapsed)
                
            except Exception as e:
                print(f"Error in chunk streaming: {e}")
                time.sleep(0.1)
    
    def cleanup(self):
        """Clean up server resources"""
        self.is_streaming = False
        
        if self.video_socket:
            self.video_socket.close()
        
        if self.control_socket:
            self.control_socket.close()
        
        print("🧹 Chunk server cleanup completed")

def main():
    # Get video file path
    video_file = input("📁 Enter video file path: ").strip()
    if not video_file:
        print("❌ No video file provided")
        return
    
    if not os.path.exists(video_file):
        print(f"❌ Video file not found: {video_file}")
        return
    
    print(f"🌐 Starting chunk-based server on IP: {SERVER_IP}")
    print("📱 Clients should connect from configured CLIENT_IP")
    
    server = ChunkBasedVideoServer(video_file_path=video_file)
    try:
        server.start_server()
    except KeyboardInterrupt:
        print("\n👋 Shutting down server...")
    finally:
        server.cleanup()

if __name__ == "__main__":
    main()
