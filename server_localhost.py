import socket
import threading
import time
import cv2
import json
import struct
import subprocess
import os
from typing import Dict, List, Tuple
import numpy as np

class VideoStreamingServer:
    def __init__(self, host='127.0.0.1', video_port=8888, control_port=8889, video_file_path=None):
        self.host = host
        self.video_port = video_port
        self.control_port = control_port
        self.video_file_path = video_file_path
        
        # Video settings for different resolutions
        self.resolutions = {
            '240p': (426, 240, 300000),      # width, height, bitrate
            '360p': (640, 360, 500000),
            '480p': (854, 480, 800000),
            '720p': (1280, 720, 2500000),
            '1080p': (1920, 1080, 5000000),
            '4K': (3840, 2160, 15000000)
        }
        
        self.current_resolution = '480p' 
        self.client_address = None  # Single client address
        self.video_source = None
        self.is_streaming = False
        self.original_fps = 30  # Default FPS
        
        # Socket setup
        self.video_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.control_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.control_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        
        print(f"Server initialized on {host}:{video_port} (video) and {control_port} (control)")
    
    def start_server(self):
        """Start the server and begin listening for connections"""
        try:
            # Bind control socket for resolution change requests
            self.is_streaming = True
            self.control_socket.bind((self.host, self.control_port))
            self.control_socket.listen(5)
            print(f"Control server listening on {self.host}:{self.control_port}")
            
            # Start control message handler in separate thread
            control_thread = threading.Thread(target=self.handle_control_connections)
            control_thread.daemon = True
            control_thread.start()
            
            # Initialize video capture
            if self.video_file_path and os.path.exists(self.video_file_path):
                print(f"Loading video file: {self.video_file_path}")
                self.video_source = cv2.VideoCapture(self.video_file_path)
                if self.video_source.isOpened():
                    # Get original video properties
                    self.original_fps = self.video_source.get(cv2.CAP_PROP_FPS)
                    total_frames = int(self.video_source.get(cv2.CAP_PROP_FRAME_COUNT))
                    duration = total_frames / self.original_fps if self.original_fps > 0 else 0
                    width = int(self.video_source.get(cv2.CAP_PROP_FRAME_WIDTH))
                    height = int(self.video_source.get(cv2.CAP_PROP_FRAME_HEIGHT))
                    
                    print(f"Video loaded successfully:")
                    print(f"  Resolution: {width}x{height}")
                    print(f"  FPS: {self.original_fps:.2f}")
                    print(f"  Duration: {duration:.2f} seconds")
                    print(f"  Total frames: {total_frames}")
                else:
                    print(f"Error: Could not open video file: {self.video_file_path}")
                    return
            else:
                print("Error: No video file specified.")
                return
            
            
            self.start_video_streaming()
            
        except Exception as e:
            print(f"Error starting server: {e}")
    
    def handle_control_connections(self):
        """Handle incoming control connections for resolution changes"""
        print(f"[DEBUG] Control connection handler thread started")
        print(f"[DEBUG] Control socket bound to {self.host}:{self.control_port}")
        print(f"[DEBUG] Control socket listening with backlog 5")
        print(f"[DEBUG] is_streaming flag: {self.is_streaming}")
        
        while self.is_streaming:
            try:
                print(f"[DEBUG] About to call accept() on control socket...")
                print(f"[DEBUG] Socket state - listening on {self.host}:{self.control_port}")
                print(f"[DEBUG] Current time: {time.time()}")
                
                # Set a timeout to avoid hanging forever
                self.control_socket.settimeout(1.0)  # 1 second timeout
                
                client_socket, addr = self.control_socket.accept()
                print(f"[DEBUG] Control connection accepted from {addr}")
                print(f"Control connection from {addr}")
                
                # Handle this client in a separate thread
                client_thread = threading.Thread(
                    target=self.handle_client_control,
                    args=(client_socket, addr)
                )
                client_thread.daemon = True
                client_thread.start()
                print(f"[DEBUG] Started client handler thread for {addr}")
                
            except socket.timeout:
                # This is expected - just continue the loop
                print(f"[DEBUG] Control socket timeout, continuing loop... is_streaming={self.is_streaming}")
                continue
            except Exception as e:
                print(f"Error in control connection: {e}")
                if self.is_streaming:  # Only print if we're still supposed to be running
                    import traceback
                    traceback.print_exc()
        
        print(f"[DEBUG] Control connection handler exiting because is_streaming={self.is_streaming}")
    
    def handle_client_control(self, client_socket, addr):
        """Handle control messages from the single client"""
        print(f"[DEBUG] Client control handler started for {addr}")
        try:
            # Register this as the active client (localhost) - use the actual client IP
            self.client_address = (addr[0], 8890)  # Use client's actual IP with video port
            print(f"[LOCALHOST] Registered single client: {self.client_address}")
            print(f"[LOCALHOST] Client control connection from: {addr}")
            
            while self.is_streaming:
                print(f"[DEBUG] Waiting for data from client {addr}")
                data = client_socket.recv(1024).decode()
                print(f"[DEBUG] Received data from {addr}: {data[:100]}...")  # First 100 chars
                if not data:
                    print(f"[DEBUG] No data received from {addr}, breaking")
                    break
                
                try:
                    message = json.loads(data)
                    print(f"[DEBUG] Parsed message type: {message.get('type', 'unknown')}")
                    if message['type'] == 'client_registration':
                        # Client is registering for video streaming
                        print(f"[LOCALHOST] Client registration received from {addr}")
                        # Registration already happened above, just acknowledge
                        response = {
                            'type': 'registration_ack',
                            'status': 'success',
                            'timestamp': time.time()
                        }
                        response_json = json.dumps(response)
                        print(f"[DEBUG] Sending response: {response_json}")
                        client_socket.send(response_json.encode())
                        print(f"[LOCALHOST] Registration acknowledged, starting video stream to {self.client_address}")
                        
                    elif message['type'] == 'resolution_request':
                        requested_resolution = message['resolution']
                        if requested_resolution in self.resolutions:
                            # Log resolution change before updating
                            if requested_resolution != self.current_resolution:
                                print(f"[OUTPUT] Stream resolution changed: {self.current_resolution} -> {requested_resolution}")
                            
                            self.current_resolution = requested_resolution
                            print(f"[RESOLUTION] Client requested resolution change to: {requested_resolution}")
                            
                            # Send acknowledgment
                            response = {
                                'type': 'resolution_ack',
                                'resolution': requested_resolution,
                                'timestamp': time.time()
                            }
                            client_socket.send(json.dumps(response).encode())
                        
                except json.JSONDecodeError as e:
                    print(f"Invalid JSON from {addr}: {e}")
                    print(f"Raw data: {data}")
                    
        except Exception as e:
            print(f"Error handling client {addr}: {e}")
            import traceback
            traceback.print_exc()
        finally:
            print(f"[DEBUG] Closing client socket for {addr}")
            client_socket.close()
            self.client_address = None
            print("[LOCALHOST] Client disconnected")
    
    def get_video_frame(self):
        """Capture video frame from file"""
        if self.video_source and self.video_source.isOpened():
            ret, frame = self.video_source.read()
            if ret:
                return frame
            else:
                # If video file ended, restart from beginning
                print("Video ended, restarting from beginning...")
                self.video_source.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ret, frame = self.video_source.read()
                if ret:
                    return frame
        
        return None
    
    def resize_frame(self, frame, resolution_key):
        """Resize frame according to resolution settings"""
        width, height, _ = self.resolutions[resolution_key]
        return cv2.resize(frame, (width, height))
    
    def encode_frame(self, frame, quality=80):
        """Encode frame as JPEG with specified quality"""
        encode_params = [cv2.IMWRITE_JPEG_QUALITY, quality]
        _, buffer = cv2.imencode('.jpg', frame, encode_params)
        return buffer.tobytes()
    
    def create_packet(self, frame_data, sequence_number, resolution):
        """Create a packet with header information"""
        timestamp = time.time()
        
        # Create header: sequence(4) + timestamp(8) + resolution_len(1) + resolution + data_len(4)
        resolution_bytes = resolution.encode()
        header = struct.pack('!I', sequence_number)  # sequence number
        header += struct.pack('!d', timestamp)       # timestamp
        header += struct.pack('!B', len(resolution_bytes))  # resolution length
        header += resolution_bytes                   # resolution string
        header += struct.pack('!I', len(frame_data)) # data length
        
        return header + frame_data
    
    def start_video_streaming(self):
        """Main video streaming loop for single client"""
        sequence_number = 0
        # Use original video FPS, but cap at 30 FPS for network efficiency
        fps = min(self.original_fps, 30) if self.original_fps > 0 else 15
        frame_delay = 1.0 / fps
        
        print(f"Starting video stream at {fps:.2f} FPS...")
        print(f"[LOCALHOST] Waiting for client to connect on localhost:{self.control_port}")
        print(f"[OUTPUT] Initial stream resolution: {self.current_resolution}")
        if self.video_file_path:
            print(f"Streaming video file: {os.path.basename(self.video_file_path)}")
        
        while self.is_streaming:
            try:
                start_time = time.time()
                
                # Get current frame
                frame = self.get_video_frame()
                if frame is None:
                    continue
                
                # Only stream if client is connected
                if self.client_address:
                    # Use current resolution (updated by client requests)
                    resolution = self.current_resolution
                    
                    # Resize and encode frame
                    resized_frame = self.resize_frame(frame, resolution)
                    
                    # Adjust quality based on resolution
                    quality_map = {
                        '240p': 60, 
                        '360p': 65, 
                        '480p': 70, 
                        '720p': 75, 
                        '1080p': 85, 
                        '4K': 90
                    }
                    encoded_frame = self.encode_frame(resized_frame, quality_map[resolution])
                    
                    # Create packet
                    packet = self.create_packet(encoded_frame, sequence_number, resolution)
                    
                    # Send to the single client
                    self.send_packet_to_client(packet)
                    
                    # Debug: Log every 100 packets
                    if sequence_number % 100 == 0:
                        print(f"[DEBUG] Sent packet #{sequence_number}, resolution: {resolution}, size: {len(packet)} bytes to {self.client_address}")
                else:
                    # Debug: Show when waiting for client
                    if sequence_number % 300 == 0:  # Every 10 seconds at 30fps
                        print(f"[DEBUG] Frame #{sequence_number} ready, waiting for client connection...")
                
                sequence_number += 1
                
                # Maintain frame rate
                elapsed = time.time() - start_time
                if elapsed < frame_delay:
                    time.sleep(frame_delay - elapsed)
                    
            except KeyboardInterrupt:
                print("\nStopping server...")
                break
            except Exception as e:
                print(f"Error in streaming loop: {e}")
        
        self.cleanup()
    
    def send_packet_to_client(self, packet):
        """Send packet to the single connected client"""
        if self.client_address:
            try:
                self.video_socket.sendto(packet, self.client_address)
            except Exception as e:
                print(f"Error sending packet to client {self.client_address}: {e}")
                # Don't disconnect client on single packet failure
    
    def cleanup(self):
        """Clean up resources"""
        self.is_streaming = False
        
        if self.video_source:
            self.video_source.release()
        
        self.video_socket.close()
        self.control_socket.close()
        
        print("[LOCALHOST] Server cleanup completed")

def main():
    import sys
    
    # Get video file path from command line argument or use default
    video_file = None
    if len(sys.argv) > 1:
        video_file = sys.argv[1]
        if not os.path.exists(video_file):
            print(f"Error: Video file '{video_file}' not found!")
            print("Usage: python server_localhost.py [path_to_video.mp4]")
            return
    else:
        # Prompt user for video file path
        print("Video Streaming Server (Localhost)")
        print("=" * 35)
        video_file = input("Enter path to video file: ").strip()
        if not video_file or not os.path.exists(video_file):
            print(f"Error: Video file '{video_file}' not found!")
            print("Usage: python server_localhost.py [path_to_video.mp4]")
            return
    
    server = VideoStreamingServer(video_file_path=video_file)
    try:
        server.start_server()
    except KeyboardInterrupt:
        print("\nShutting down server...")
    finally:
        server.cleanup()

if __name__ == "__main__":
    main()
