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
from config import INITIAL_RESOLUTION

class ChunkBasedVideoServer:
    def __init__(self, host='127.0.0.1', video_port=8888, control_port=8889, video_file_path=None):
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
            self.start_chunk_streaming()
            
        except Exception as e:
            print(f"Error starting server: {e}")
    
    def handle_control_connections(self):
        """Handle incoming control connections"""
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
                    print(f"Error in control connection: {e}")
    
    def handle_client_control(self, client_socket, addr):
        """Handle control messages from a client"""
        try:
            # Register client with default settings
            self.clients[addr] = {
                'resolution': INITIAL_RESOLUTION,
                'current_chunk': 0,
                'socket': client_socket
            }
            
            print(f"📱 Client {addr} registered with default resolution: {INITIAL_RESOLUTION}")
            
            # Send registration acknowledgment
            response = {
                'type': 'registration_ack',
                'status': 'success',
                'total_chunks': self.total_chunks,
                'chunk_duration': self.chunk_duration
            }
            client_socket.send(json.dumps(response).encode())
            
            while self.is_streaming:
                data = client_socket.recv(1024).decode()
                if not data:
                    break
                
                try:
                    message = json.loads(data)
                    
                    if message['type'] == 'resolution_request':
                        requested_resolution = message['resolution']
                        if requested_resolution in self.resolutions:
                            old_resolution = self.clients[addr]['resolution']
                            self.clients[addr]['resolution'] = requested_resolution
                            print(f"🎯 Client {addr} resolution: {old_resolution} → {requested_resolution}")
                            
                            # Send acknowledgment
                            response = {
                                'type': 'resolution_ack',
                                'resolution': requested_resolution,
                                'timestamp': time.time()
                            }
                            client_socket.send(json.dumps(response).encode())
                    
                    elif message['type'] == 'chunk_request':
                        # Client requesting specific chunk
                        chunk_id = message.get('chunk_id', 0)
                        if 0 <= chunk_id < self.total_chunks:
                            self.clients[addr]['current_chunk'] = chunk_id
                            print(f"📦 Client {addr} requesting chunk {chunk_id}")
                        
                except json.JSONDecodeError:
                    print(f"❌ Invalid JSON from {addr}")
                    
        except Exception as e:
            print(f"Error handling client {addr}: {e}")
        finally:
            client_socket.close()
            if addr in self.clients:
                del self.clients[addr]
                print(f"👋 Client {addr} disconnected")
    
    def create_chunk_packets(self, frame_data, sequence_number, chunk_id, frame_index, resolution):
        """Create packets for chunk-based streaming with fragmentation support"""
        timestamp = time.time()
        resolution_bytes = resolution.encode()
        
        # Calculate maximum payload size (leaving room for headers)
        max_packet_size = 60000  # Safe UDP packet size for Windows
        base_header_size = 4 + 8 + 4 + 4 + 1 + len(resolution_bytes) + 4 + 4 + 4  # Added fragment info
        max_payload_size = max_packet_size - base_header_size
        
        packets = []
        total_fragments = (len(frame_data) + max_payload_size - 1) // max_payload_size
        
        # Log fragmentation for high-resolution frames
        if total_fragments > 1:
            print(f"🔧 Fragmenting {resolution} frame into {total_fragments} packets ({len(frame_data)} bytes)")
        
        for fragment_index in range(total_fragments):
            start_pos = fragment_index * max_payload_size
            end_pos = min(start_pos + max_payload_size, len(frame_data))
            fragment_data = frame_data[start_pos:end_pos]
            
            # Create header with fragmentation info:
            # sequence(4) + timestamp(8) + chunk_id(4) + frame_index(4) + resolution_len(1) + resolution + 
            # total_fragments(4) + fragment_index(4) + fragment_size(4) + fragment_data
            header = struct.pack('!I', sequence_number + fragment_index)  # unique sequence per fragment
            header += struct.pack('!d', timestamp)                       # timestamp
            header += struct.pack('!I', chunk_id)                        # chunk ID
            header += struct.pack('!I', frame_index)                     # frame index within chunk
            header += struct.pack('!B', len(resolution_bytes))           # resolution length
            header += resolution_bytes                                    # resolution string
            header += struct.pack('!I', total_fragments)                 # total fragments for this frame
            header += struct.pack('!I', fragment_index)                  # current fragment index
            header += struct.pack('!I', len(fragment_data))              # fragment data length
            
            packets.append(header + fragment_data)
        
        return packets
    
    def start_chunk_streaming(self):
        """Main chunk streaming loop"""
        sequence_number = 0
        frame_delay = 1.0 / self.original_fps
        
        print(f"🎬 Starting chunk-based streaming at {self.original_fps:.2f} FPS")
        print(f"📊 Total chunks: {self.total_chunks}, Duration per chunk: {self.chunk_duration}s (2-second chunks)")
        print(f"⚡ Faster chunk switching for responsive streaming")
        
        while self.is_streaming:
            try:
                # Process each client
                for addr, client_info in list(self.clients.items()):
                    resolution = client_info['resolution']
                    chunk_id = client_info['current_chunk']
                    
                    # Load chunk if needed
                    chunk_frames = self.load_chunk(resolution, chunk_id)
                    if chunk_frames is None:
                        # Move to next chunk or loop back to beginning
                        if chunk_id >= self.total_chunks - 1:
                            client_info['current_chunk'] = 0
                        else:
                            client_info['current_chunk'] += 1
                        continue
                    
                    # Send frames from current chunk
                    for frame_index, frame_data in enumerate(chunk_frames):
                        start_time = time.time()
                        
                        # Create fragmented packets for large frames
                        packets = self.create_chunk_packets(
                            frame_data, sequence_number, chunk_id, frame_index, resolution
                        )
                        
                        # Send all fragments for this frame
                        for packet in packets:
                            try:
                                client_address = (addr[0], 8890)  # Assuming client video port
                                self.video_socket.sendto(packet, client_address)
                            except Exception as e:
                                print(f"Error sending fragment to {addr}: {e}")
                                break
                        
                        sequence_number += len(packets)  # Increment by number of fragments sent
                        
                        # Maintain frame rate
                        elapsed = time.time() - start_time
                        if elapsed < frame_delay:
                            time.sleep(frame_delay - elapsed)
                    
                    # Move to next chunk
                    if chunk_id >= self.total_chunks - 1:
                        client_info['current_chunk'] = 0  # Loop back to beginning
                        print(f"🔄 Client {addr} looping back to chunk 0")
                    else:
                        client_info['current_chunk'] += 1
                
                # If no clients, just wait
                if not self.clients:
                    time.sleep(0.1)
                    
            except KeyboardInterrupt:
                print("\n🛑 Stopping server...")
                break
            except Exception as e:
                print(f"Error in streaming loop: {e}")
        
        self.cleanup()
    
    def cleanup(self):
        """Clean up resources"""
        self.is_streaming = False
        
        # Close sockets
        try:
            self.video_socket.close()
            self.control_socket.close()
        except:
            pass
        
        # Close client connections
        for client_info in self.clients.values():
            try:
                client_info['socket'].close()
            except:
                pass
        
        print("🧹 Server cleanup completed")

def main():
    import sys
    
    # Get video file path
    video_file = None
    if len(sys.argv) > 1:
        video_file = sys.argv[1]
        if not os.path.exists(video_file):
            print(f"❌ Error: Video file '{video_file}' not found!")
            print("Usage: python server_chunk.py [path_to_video.mp4]")
            return
    else:
        print("🎥 Chunk-based Video Streaming Server")
        print("=" * 40)
        video_file = input("Enter path to video file: ").strip().strip('"')
        if not video_file or not os.path.exists(video_file):
            print(f"❌ Error: Video file '{video_file}' not found!")
            return
    
    server = ChunkBasedVideoServer(video_file_path=video_file)
    try:
        server.start_server()
    except KeyboardInterrupt:
        print("\n👋 Shutting down server...")
    finally:
        server.cleanup()

if __name__ == "__main__":
    main()
