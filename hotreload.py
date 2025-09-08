#!/usr/bin/env python3
# /// script
# dependencies = [
#   "watchdog",
# ]
# ///

import os
import sys
import time
import subprocess
import argparse
import glob
import threading
import socket
import http.server
import socketserver
import shutil
from pathlib import Path

try:
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler
except ImportError:
    print("❌ 'watchdog' package is required")
    print("💡 Run with: uv run hotreload.py")
    sys.exit(1)

DEFAULT_PORT = 8000
WATCH_DIR = "."
PUBLIC_DIR = "./public"
BUILD_SCRIPT = "./build.sh"


def find_available_port(start_port=DEFAULT_PORT, max_attempts=10):
    """Find an available port starting from start_port"""
    for port in range(start_port, start_port + max_attempts):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.bind(('', port))
                return port
        except OSError:
            continue
    return start_port  # Fallback to original port if all fail


class CustomHTTPRequestHandler(http.server.SimpleHTTPRequestHandler):
    """Custom HTTP request handler that serves from PUBLIC_DIR with refresh support"""
    
    # Class-level variables for SSE functionality
    clients = set()
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=PUBLIC_DIR, **kwargs)
    
    def log_message(self, format, *args):
        # Disable default logging for cleaner output
        pass
    
    def do_GET(self):
        """Handle GET requests with SSE endpoint and HTML injection"""
        if self.path == '/__events__':
            self.handle_sse()
        else:
            self.handle_regular_request()
    
    def handle_sse(self):
        """Handle Server-Sent Events endpoint"""
        self.send_response(200)
        self.send_header('Content-type', 'text/event-stream')
        self.send_header('Cache-Control', 'no-cache')
        self.send_header('Connection', 'keep-alive')
        self.end_headers()
        
        # Add this client to the set
        self.clients.add(self.wfile)
        
        try:
            # Keep connection alive for SSE
            while True:
                time.sleep(1)
                # Send periodic keep-alive message (comments are ignored by clients)
                try:
                    self.wfile.write(b':keepalive\n\n')
                    self.wfile.flush()
                except:
                    break
        except:
            pass
        finally:
            # Remove client when connection drops
            self.clients.discard(self.wfile)
    
    def handle_regular_request(self):
        """Handle regular HTTP requests with HTML injection"""
        path = self.translate_path(self.path)
        
        # Only inject refresh script for HTML files
        if path.endswith('.html') and os.path.exists(path):
            try:
                with open(path, 'rb') as f:
                    content = f.read()
                
                # Inject refresh script before </body> tag
                refresh_script = b'<!-- Hot Reload Script -->\n<script>const source = new EventSource("/__events__"); source.addEventListener("reload", () => location.reload()); source.onerror = e => console.error("SSE error:", e);</script>\n'
                
                # Replace closing body tag (case-insensitive)
                body_tag = b'</body>'
                body_position = content.lower().rfind(b'</body>')
                if body_position != -1:
                    updated_content = content[:body_position] + refresh_script + content[body_position:]
                else:
                    # Fallback: append at end of file if no body tag found
                    updated_content = content + refresh_script
                
                # Send headers
                self.send_response(200)
                self.send_header('Content-type', 'text/html')
                self.send_header('Content-Length', str(len(updated_content)))
                self.end_headers()
                
                # Send modified content
                self.wfile.write(updated_content)
                return
                
            except Exception as e:
                # Fallback to default behavior if injection fails
                pass
        
        # Fallback to default handler
        super().do_GET()
    
    @classmethod
    def send_refresh_event(cls):
        """Send refresh event to all connected clients"""
        refresh_message = b'event: reload\ndata: true\n\n'
        disconnected_clients = set()
        connected_count = 0
        
        for client in cls.clients.copy():
            try:
                client.write(refresh_message)
                client.flush()
                connected_count += 1
            except:
                disconnected_clients.add(client)
        
        # Remove disconnected clients
        cls.clients -= disconnected_clients
        
        if connected_count > 0:
            print(f"🔄 Browser refresh events sent to {connected_count} client(s)")
        else:
            print("⚠️  No connected browsers to refresh")


def start_http_server(port):
    """Start HTTP server in a separate thread"""
    try:
        # Check if public directory exists
        if not os.path.exists(PUBLIC_DIR):
            print(f"⚠️  Public directory {PUBLIC_DIR} does not exist")
            print("💡 Run with --initial-build to create it")
            return
        
        # Create server
        with socketserver.TCPServer(("", port), CustomHTTPRequestHandler) as httpd:
            print(f"🌐 HTTP server running at http://localhost:{port}")
            print(f"📁 Serving files from: {os.path.abspath(PUBLIC_DIR)}")
            print(f"💡 Refresh your browser to see changes\n")
            
            # Serve until interrupted
            httpd.serve_forever()
            
    except OSError as e:
        if "Address already in use" in str(e):
            print(f"❌ Port {port} is already in use")
            available_port = find_available_port(port + 1)
            if available_port != port:
                print(f"🔄 Trying port {available_port}...")
                start_http_server(available_port)
            else:
                print(f"❌ No available ports found")
        else:
            print(f"❌ HTTP server error: {e}")
    except Exception as e:
        print(f"❌ HTTP server unexpected error: {e}")


class BuildHandler(FileSystemEventHandler):
    def __init__(self):
        self.last_build = 0
        self.build_cooldown = 0  # seconds - rebuild immediately on every change
        self.is_building = False

    def _clean_emacs_cache(self):
        """Clean Emacs cache files to prevent lock conflicts"""
        cache_files = [
            "~/.org-timestamps/pages.cache",
            "~/.org-timestamps/posts.cache", 
            "~/.emacs.d/.cache/org-timestamps",
            "~/.emacs.d/.cache/org",
            "#*#"  # auto-save files
        ]
        
        cleaned_count = 0
        for cache_pattern in cache_files:
            try:
                if '#' in cache_pattern:
                    # Handle auto-save file patterns
                    for cache_file in glob.glob(os.path.expanduser(cache_pattern)):
                        try:
                            os.remove(cache_file)
                            cleaned_count += 1
                        except (FileNotFoundError, OSError):
                            continue
                else:
                    # Handle specific files
                    cache_file = os.path.expanduser(cache_pattern)
                    if os.path.exists(cache_file):
                        os.remove(cache_file)
                        cleaned_count += 1
            except (PermissionError, FileNotFoundError, OSError):
                # Ignore permission errors or files that don't exist
                pass
            except Exception as e:
                print(f"⚠️  Failed to clean cache {cache_pattern}: {e}")
        
        if cleaned_count > 0:
            print(f"🗑️  Cleaned {cleaned_count} cache files")
        
        # Also kill orphaned Emacs processes that might hold locks
        try:
            subprocess.run("pkill -f 'emacs.*batch'", shell=True, 
                         capture_output=True, text=True)
        except:
            pass

    def run_build(self):
        """Execute build script with retry logic for lock conflicts"""
        # Mark build as in progress to prevent circular builds
        if self.is_building:
            print("⚠️  Build already in progress, skipping...")
            return
            
        self.is_building = True
        build_success = False

        try:
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    print(f"🔨 Running build script: {BUILD_SCRIPT}")
                    if attempt > 0:
                        print(f"🔄 Attempt {attempt + 1}/{max_retries}")
                    
                    # Clean Emacs cache files before building
                    print("🧹 Cleaning Emacs cache files...")
                    self._clean_emacs_cache()
                    
                    # Add exponential backoff for retries
                    if attempt > 0:
                        sleep_time = min(2 ** attempt, 8)  # Max 8 seconds
                        print(f"⏳ Waiting {sleep_time} seconds before retry...")
                        time.sleep(sleep_time)
                    
                    # Remove public directory completely before building
                    if os.path.exists(PUBLIC_DIR):
                        print(f"🗑️  Removing existing public directory: {PUBLIC_DIR}")
                        try:
                            import shutil
                            shutil.rmtree(PUBLIC_DIR)
                            print(f"✅ Public directory removed successfully")
                        except Exception as e:
                            print(f"⚠️  Failed to remove public directory: {e}")
                    else:
                        print(f"📁 No existing public directory found")
                    
                    result = subprocess.run(
                        [BUILD_SCRIPT],
                        shell=True,
                        capture_output=True,
                        text=True,
                        cwd=os.getcwd()
                    )
                    
                    if result.returncode == 0:
                        # Build succeeded
                        build_success = True
                        print("✅ Build completed successfully")
                        
                        # Verify public directory exists after build
                        if os.path.exists(PUBLIC_DIR):
                            print("✅ Build output created")
                            # Send refresh event to all connected clients
                            try:
                                CustomHTTPRequestHandler.send_refresh_event()
                                print("🔄 Browser refresh events sent")
                            except Exception as e:
                                print(f"⚠️  Failed to send refresh events: {e}")
                        else:
                            print(f"❌ Build succeeded but {PUBLIC_DIR} directory was not created")
                        
                        break
                    else:
                        # Build failed
                        if "Cannot resolve lock conflict" in result.stderr:
                            if attempt < max_retries - 1:
                                print(f"⚠️  Lock conflict detected, retrying...")
                                continue
                            else:
                                print(f"❌ Lock conflict unresolved after {max_retries} attempts")
                        
                        print(f"❌ Build failed with exit code {result.returncode}")
                        if result.stderr:
                            print(f"❌ Error: {result.stderr}")
                        if result.stdout:
                            print(f"💡 Build output: {result.stdout[:200]}...")
                        
                        break
                        
                except Exception as e:
                    print(f"❌ Build error: {e}")
                    break
                    
        except Exception as e:
            print(f"❌ Build critical error: {e}")
        finally:
            # Reset build state
            self.is_building = False
            return build_success

    def on_modified(self, event):
        if event.is_directory:
            return

        # Skip files changed during build process to prevent circular builds
        if self.is_building:
            return

        # Check if file has relevant extension or is build script
        file_path = Path(event.src_path)
        
        # Skip Emacs lock files (files starting with .#)
        if file_path.name.startswith(".#"):
            return
            
        # Skip files generated by the build process to prevent circular builds
        if file_path.name in ["build.el"] or str(file_path).endswith("/posts/posts.org"):
            return
            
        # Skip everything in public directory (output directory)
        try:
            # Use Path.resolve() to get absolute path for reliable comparison
            public_dir = Path(PUBLIC_DIR).resolve()
            file_path_abs = file_path.resolve()
            
            # Check if file is within public directory
            if file_path_abs == public_dir or file_path_abs.is_relative_to(public_dir):
                return
        except (ValueError, OSError):
            # Fallback to string comparison if Path operations fail
            file_path_str = str(file_path)
            if (file_path_str.startswith("./public/") or 
                file_path_str.startswith("public/") or
                file_path_str.startswith("/public/") or
                "/public/" in file_path_str):
                return
            
        # Watch .org files, build script, .el files, and asset files (CSS/JS)
        if (file_path.suffix == ".org" 
            or file_path.name == "build.sh"
            or file_path.name.endswith(".el")
            or file_path.suffix in [".css", ".js"]):
            
            print(f"\n🔄 File changed: {event.src_path}")
            self.run_build()


def main():
    """Main function to handle file watcher and HTTP server setup"""
    parser = argparse.ArgumentParser(description='Hot Reload: Automatic builds + browser refresh (watches .org, .el, .css, .js files and build.sh)')
    parser.add_argument('--initial-build', action='store_true',
                        help='Run initial build before starting to watch')
    parser.add_argument('--no-server', action='store_true',
                        help='Disable HTTP server (build watcher only)')
    args = parser.parse_args()

    # Ensure build script is executable
    if os.path.exists(BUILD_SCRIPT):
        print(f"🔧 Making {BUILD_SCRIPT} executable...")
        os.chmod(BUILD_SCRIPT, 0o755)

    # Run initial build if requested
    if args.initial_build:
        handler = BuildHandler()
        print("🏗️  Running initial build...")
        handler.run_build()
        print("📋 Initial build completed\n")

    # Start HTTP server unless disabled
    http_thread = None
    if not args.no_server:
        # Find available port
        port = find_available_port(DEFAULT_PORT)
        
        # Start HTTP server in separate thread
        http_thread = threading.Thread(target=start_http_server, args=(port,), daemon=True)
        http_thread.start()
        
        # Give server time to start
        time.sleep(0.5)

    # Create file watcher
    handler = BuildHandler()
    observer = Observer()
    
    print("🚀 Starting hot reload system...")
    print(f"📁 Watching directory: {os.path.abspath(WATCH_DIR)}")
    print(f"🎯 Watching for: .org files, build.sh, .el files, and asset files (.css/.js)")
    print(f"🗑️  Skipping: Emacs lock files, build-generated files, all files in {PUBLIC_DIR}")
    if not args.no_server:
        print(f"🌐 Browser auto-refresh enabled - no manual refresh needed!")
    print("⌨️  Press Ctrl+C to stop\n")
    
    observer.schedule(handler, WATCH_DIR, recursive=True)
    observer.start()
    
    try:
        print("⏳ Waiting for file changes...\n")
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
        observer.stop()
        observer.join()
        print("✅ Hot reload stopped")


if __name__ == "__main__":
    main()