import subprocess
import socket
import os
import sys

def check_ffmpeg_installation():
    """Check if FFmpeg is properly installed"""
    print("🔍 Checking FFmpeg installation...")
    
    try:
        # Check FFmpeg
        result = subprocess.run(['ffmpeg', '-version'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            version = result.stdout.split('\n')[0]
            print(f"✅ FFmpeg found: {version}")
        else:
            print("❌ FFmpeg found but not working properly")
            return False
    except FileNotFoundError:
        print("❌ FFmpeg not found in PATH")
        print("📋 Install FFmpeg using one of these methods:")
        print("   1. winget install Gyan.FFmpeg")
        print("   2. Download from https://www.gyan.dev/ffmpeg/builds/")
        print("   3. choco install ffmpeg (if you have Chocolatey)")
        return False
    except subprocess.TimeoutExpired:
        print("❌ FFmpeg check timed out")
        return False
    
    try:
        # Check FFplay
        result = subprocess.run(['ffplay', '-version'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print("✅ FFplay found and working")
        else:
            print("❌ FFplay found but not working properly")
            return False
    except FileNotFoundError:
        print("❌ FFplay not found in PATH")
        return False
    
    try:
        # Check FFprobe
        result = subprocess.run(['ffprobe', '-version'], 
                              capture_output=True, text=True, timeout=5)
        if result.returncode == 0:
            print("✅ FFprobe found and working")
            return True
        else:
            print("❌ FFprobe found but not working properly")
            return False
    except FileNotFoundError:
        print("❌ FFprobe not found in PATH")
        return False

def check_ports():
    """Check if required ports are available"""
    print("\n🔍 Checking port availability...")
    
    ports_to_check = [8889, 8890]  # control_port, video_port
    
    for port in ports_to_check:
        try:
            # Check TCP port (control)
            if port == 8889:
                sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                sock.bind(('localhost', port))
                sock.close()
                print(f"✅ TCP Port {port} is available")
            
            # Check UDP port (video)
            if port == 8890:
                sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                sock.bind(('localhost', port))
                sock.close()
                print(f"✅ UDP Port {port} is available")
                
        except OSError as e:
            print(f"❌ Port {port} is in use or blocked: {e}")
            return False
    
    return True

def find_video_files():
    """Find available video files in current directory only"""
    print("\n🔍 Looking for video files in current directory...")
    
    video_extensions = ['.mp4', '.avi', '.mkv', '.mov', '.wmv', '.flv', '.webm', '.m4v']
    current_dir = os.getcwd()  # Only search current directory
    
    found_videos = []
    
    print(f"🔍 Searching in: {current_dir}")
    try:
        for file in os.listdir(current_dir):
            if any(file.lower().endswith(ext) for ext in video_extensions):
                full_path = os.path.join(current_dir, file)
                if os.path.isfile(full_path):
                    size_mb = os.path.getsize(full_path) / (1024 * 1024)
                    found_videos.append((full_path, size_mb))
                    print(f"   📹 {file} ({size_mb:.1f} MB)")
    except PermissionError:
        print(f"   ⚠️ Permission denied accessing current directory")
    
    if found_videos:
        print(f"\n✅ Found {len(found_videos)} video file(s) in current directory")
        return found_videos
    else:
        print("❌ No video files found in current directory")
        print("💡 Please place a video file (.mp4, .avi, .mkv, etc.) in the current directory")
        return []

def test_video_file(video_path):
    """Test if a video file can be processed by FFmpeg"""
    print(f"\n🔍 Testing video file: {os.path.basename(video_path)}")
    
    if not os.path.exists(video_path):
        print("❌ File does not exist")
        return False
    
    try:
        # Get file info using FFprobe
        cmd = [
            'ffprobe', '-v', 'quiet', '-print_format', 'json',
            '-show_format', '-show_streams', video_path
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            import json
            info = json.loads(result.stdout)
            video_stream = next((s for s in info['streams'] if s['codec_type'] == 'video'), None)
            
            if video_stream:
                width = video_stream.get('width', 'unknown')
                height = video_stream.get('height', 'unknown')
                fps = video_stream.get('r_frame_rate', '30/1')
                duration = float(info['format'].get('duration', 0))
                codec = video_stream.get('codec_name', 'unknown')
                
                print(f"✅ Video file is valid:")
                print(f"   Resolution: {width}x{height}")
                print(f"   FPS: {fps}")
                print(f"   Duration: {duration:.2f} seconds")
                print(f"   Codec: {codec}")
                
                return True
            else:
                print("❌ No video stream found in file")
                return False
        else:
            print(f"❌ FFprobe failed: {result.stderr}")
            return False
            
    except Exception as e:
        print(f"❌ Error testing video file: {e}")
        return False

def run_server_test(video_path):
    """Test running the server with a specific video file"""
    print(f"\n🔍 Testing server startup with: {os.path.basename(video_path)}")
    
    try:
        # Import and test server
        from server_ffmpeg import FFmpegVideoServer
        
        server = FFmpegVideoServer(video_file_path=video_path)
        
        # Test FFmpeg check
        if not server.check_ffmpeg():
            print("❌ FFmpeg check failed")
            return False
        
        # Test video info
        if not server.get_video_info():
            print("❌ Video info check failed")
            return False
        
        print("✅ Server initialization test passed")
        return True
        
    except ImportError as e:
        print(f"❌ Could not import server: {e}")
        return False
    except Exception as e:
        print(f"❌ Server test failed: {e}")
        return False

def main():
    print("🔧 FFmpeg Video Streaming - Diagnostic Tool")
    print("=" * 50)
    
    all_checks_passed = True
    
    # Check 1: FFmpeg installation
    if not check_ffmpeg_installation():
        all_checks_passed = False
    
    # Check 2: Port availability
    if not check_ports():
        all_checks_passed = False
    
    # Check 3: Find video files
    video_files = find_video_files()
    if not video_files:
        all_checks_passed = False
    
    # Check 4: Test video files
    valid_videos = []
    for video_path, size_mb in video_files[:3]:  # Test first 3 files
        if test_video_file(video_path):
            valid_videos.append(video_path)
    
    if not valid_videos:
        print("\n❌ No valid video files found")
        all_checks_passed = False
    
    # Check 5: Test server
    if valid_videos:
        test_video = valid_videos[0]
        if not run_server_test(test_video):
            all_checks_passed = False
    
    # Final result
    print("\n" + "=" * 50)
    if all_checks_passed:
        print("✅ All diagnostics passed! Your system should work.")
        if valid_videos:
            print(f"\n🎯 Recommended video file: {os.path.basename(valid_videos[0])}")
            print(f"📍 Full path: {valid_videos[0]}")
    else:
        print("❌ Some issues were found. Please fix them before running the server.")
    
    print("\n🔧 Troubleshooting Tips:")
    print("1. Make sure FFmpeg is in your PATH")
    print("2. Try a different video file if current one fails")
    print("3. Check Windows Firewall settings for ports 8889/8890")
    print("4. Run as Administrator if you have permission issues")
    print("5. Close any other applications using the same ports")

if __name__ == "__main__":
    main()