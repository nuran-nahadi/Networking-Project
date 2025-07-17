# Installation Guide for Video Streaming Server-Client Setup

## Quick Installation

### 1. Install Python Dependencies
```bash
# Install required Python packages
pip install -r requirements.txt

# Or install manually:
pip install opencv-python>=4.8.0 numpy>=1.24.0
```

### 2. Install FFmpeg (Required for FFmpeg-based streaming)

**Windows:**
- Download FFmpeg from https://ffmpeg.org/download.html
- Extract to a folder (e.g., `C:\ffmpeg`)
- Add `C:\ffmpeg\bin` to your system PATH
- Verify: `ffmpeg -version`

**macOS:**
```bash
brew install ffmpeg
```

**Ubuntu/Debian:**
```bash
sudo apt update
sudo apt install ffmpeg
```

**CentOS/RHEL:**
```bash
sudo yum install ffmpeg
```

### 3. Verify Installation
```bash
# Check Python packages
python -c "import cv2, numpy; print('OpenCV:', cv2.__version__); print('NumPy:', numpy.__version__)"

# Check FFmpeg
ffmpeg -version
```

## System Requirements

- **Python**: 3.8 or higher
- **Operating System**: Windows 10/11, macOS 10.14+, Linux
- **RAM**: Minimum 4GB (8GB recommended for 4K streaming)
- **Network**: Stable network connection for client-server communication
- **Video Files**: Any format supported by OpenCV/FFmpeg (MP4, AVI, MOV, etc.)

## Project Structure

```
Networking Project/
├── requirements.txt           # Python dependencies
├── INSTALL.md                # This installation guide
├── server.py                 # OpenCV-based server
├── client.py                 # OpenCV-based client  
├── server_ffmpeg.py          # FFmpeg-based server (recommended)
├── client_ffmpeg.py          # FFmpeg-based client (recommended)
└── launcher_ffmpeg.py        # Easy launcher for FFmpeg system
```

## Usage

### OpenCV-based System:
```bash
# Terminal 1 - Start server
python server.py

# Terminal 2 - Start client  
python client.py
```

### FFmpeg-based System (Recommended):
```bash
# Easy launcher
python launcher_ffmpeg.py

# Or manually:
# Terminal 1 - Start server
python server_ffmpeg.py

# Terminal 2 - Start client
python client_ffmpeg.py
```

## Network Configuration

- **Server IP**: 10.42.0.13
- **Client IP**: 10.42.0.176
- **Video Port**: 8890 (UDP)
- **Control Port**: 8889 (TCP)

Make sure these ports are open in your firewall settings.

## Troubleshooting

1. **ImportError: No module named 'cv2'**
   - Run: `pip install opencv-python`

2. **FFmpeg not found error**
   - Install FFmpeg and add to PATH
   - Verify with: `ffmpeg -version`

3. **Connection refused errors**
   - Check IP addresses in code match your network
   - Ensure ports 8889 and 8890 are not blocked by firewall

4. **Permission denied on Linux/macOS**
   - Run with: `python3` instead of `python`
   - May need: `sudo` for some network operations
