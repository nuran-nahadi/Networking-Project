# Video Streaming Application with Dynamic Resolution Adaptation

This project implements a real-time video streaming application with dynamic resolution switching based on network conditions, as described in the project proposal.

## Features

- **Server-side multi-resolution encoding**: Dynamically encodes video in low (320x240), medium (640x480), and high (1280x720) resolutions
- **Client-side network monitoring**: Real-time analysis of latency, jitter, packet loss, and throughput
- **Adaptive resolution switching**: Intelligent algorithm that adjusts video quality based on network conditions
- **Real-time visualization**: Live plots of network metrics and streaming performance
- **Packet-level analysis**: Detailed monitoring of video stream packets for precise network assessment

## Installation

1. **Install Python dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Install FFmpeg** (optional, for advanced encoding):
   - Windows: Download from https://ffmpeg.org/download.html
   - Add FFmpeg to your system PATH

## Usage

### Starting the Server

1. Run the server:
   ```bash
   python server.py
   ```

2. The server will:
   - Start listening on port 8888 for video streaming (UDP)
   - Start listening on port 8889 for control messages (TCP)
   - Begin capturing video from your webcam (or use test pattern if no camera)

### Starting the Client

1. Run the client:
   ```bash
   python client.py
   ```

2. The client will:
   - Connect to the server
   - Display the video stream in an OpenCV window
   - Show real-time network metrics overlay on the video
   - Display live plots of network performance metrics
   - Automatically adapt resolution based on network conditions

### Bandwidth Limitation Testing

To test the adaptive resolution feature, you can limit your network bandwidth using these methods:

#### Windows (using built-in tools):

1. **Using Windows QoS Policy** (requires admin privileges):
   ```powershell
   # Run as Administrator
   netsh interface tcp set global autotuninglevel=disabled
   netsh interface ipv4 set subinterface "Local Area Connection" mtu=576 store=persistent
   ```

2. **Using PowerShell traffic shaping**:
   ```powershell
   # Limit bandwidth to 1 Mbps (adjust as needed)
   New-NetQosPolicy -Name "VideoStreamLimit" -AppPathNameMatchCondition "python.exe" -ThrottleRateActionBitsPerSecond 1MB
   ```

#### Using third-party tools:

1. **Clumsy** (Recommended for Windows):
   - Download from: http://jagt.github.io/clumsy/
   - Set lag, drop packets, or limit bandwidth for specific applications

2. **NetLimiter** (Commercial):
   - Provides precise bandwidth control per application

#### Linux alternatives:
```bash
# Using tc (traffic control) to limit bandwidth
sudo tc qdisc add dev eth0 root handle 1: htb default 30
sudo tc class add dev eth0 parent 1: classid 1:1 htb rate 1mbit
sudo tc class add dev eth0 parent 1:1 classid 1:10 htb rate 1mbit ceil 1mbit
```

## Understanding the Adaptation Algorithm

The client monitors these network metrics:

- **Latency**: Round-trip time between client and server
- **Jitter**: Variation in packet arrival times
- **Packet Loss**: Percentage of lost packets
- **Throughput**: Data transfer rate

### Resolution Switching Logic:

**Downgrade conditions** (high → medium → low):
- Latency > 200ms
- Jitter > 50ms
- Packet loss > 2%
- Throughput < 50 KB/s

**Upgrade conditions** (low → medium → high):
- Latency < 50ms
- Jitter < 25ms
- Packet loss < 1%
- Throughput > 200 KB/s

## File Structure

```
├── server.py              # Video streaming server
├── client.py              # Video streaming client with adaptation
├── requirements.txt       # Python dependencies
└── README.md             # This file
```

## Customization

### Modifying Resolution Settings

Edit the `resolutions` dictionary in `server.py`:

```python
self.resolutions = {
    'low': (320, 240, 300000),      # width, height, bitrate
    'medium': (640, 480, 800000),
    'high': (1280, 720, 2000000),
    'ultra': (1920, 1080, 4000000)  # Add new resolution
}
```

### Adjusting Adaptation Thresholds

Modify the thresholds in `client.py`:

```python
self.thresholds = {
    'latency_high': 200,      # ms
    'latency_low': 50,        # ms
    'jitter_high': 50,        # ms
    'packet_loss_high': 2.0,  # %
    'throughput_low': 50000,  # bytes/sec
    'throughput_high': 200000 # bytes/sec
}
```

### Using Different Video Sources

In `server.py`, modify the video source:

```python
# For webcam (default)
self.video_source = cv2.VideoCapture(0)

# For video file
self.video_source = cv2.VideoCapture('path/to/video/file.mp4')

# For IP camera
self.video_source = cv2.VideoCapture('rtsp://camera_ip:port/stream')
```

## Troubleshooting

### Common Issues:

1. **"Import cv2 could not be resolved"**:
   ```bash
   pip install opencv-python
   ```

2. **"No video source available"**:
   - Check if your webcam is working
   - Try changing camera index: `cv2.VideoCapture(1)` instead of `cv2.VideoCapture(0)`

3. **Client cannot connect to server**:
   - Ensure server is running first
   - Check firewall settings
   - Verify IP address and port configuration

4. **Poor video quality**:
   - Adjust JPEG quality settings in `encode_frame()`
   - Modify resolution and bitrate settings

### Performance Tips:

- Close unnecessary applications to reduce CPU usage
- Use wired connection instead of WiFi for more stable testing
- Adjust frame rate in the server's `start_video_streaming()` method
- Monitor system resources using the built-in psutil integration

## Network Testing Scenarios

1. **Stable Network**: All metrics should remain stable, resolution should stay high
2. **High Latency**: Introduce 200ms+ delay, should trigger downgrade
3. **Packet Loss**: Drop 3%+ packets, should trigger downgrade
4. **Bandwidth Limitation**: Limit to < 100 KB/s, should trigger downgrade
5. **Recovery**: Remove limitations, should gradually upgrade resolution

## Future Enhancements

- Integration with FFmpeg for hardware-accelerated encoding
- Support for multiple simultaneous clients
- Advanced prediction algorithms for proactive adaptation
- Integration with network emulation tools
- Web-based control interface using Flask
- Support for different video codecs (H.264, VP9, etc.)
