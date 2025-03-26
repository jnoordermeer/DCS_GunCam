import sys
import json
import pygame
import os
import cv2
import numpy as np
import mss
import time
from datetime import datetime
import configparser
from pathlib import Path
import win32gui  # Voor actief venster detectie
import base64
from io import BytesIO
from PIL import Image
import ctypes
from PyQt6.QtWidgets import (QApplication, QMainWindow, QPushButton, QVBoxLayout, 
                            QWidget, QMessageBox, QLabel, QFileDialog, QHBoxLayout, QSpinBox, QGroupBox, QProgressBar,
                            QComboBox, QLineEdit)
from PyQt6.QtCore import QThread, pyqtSignal, Qt, QTimer
from PyQt6.QtGui import QPalette, QColor, QIcon, QPixmap
import win32con  # Voor stijl van het venster
import win32api  # Voor monitor informatie

# DWM constanten voor Windows 11 dark title bar
DWMWA_USE_IMMERSIVE_DARK_MODE = 20
dwmapi = ctypes.WinDLL("dwmapi")

# Minimaliseer CMD venster bij startup
kernel32 = ctypes.WinDLL('kernel32')
user32 = ctypes.WinDLL('user32')
SW_MINIMIZE = 6
hwnd = kernel32.GetConsoleWindow()
if hwnd:
    user32.ShowWindow(hwnd, SW_MINIMIZE)

def set_titlebar_color(hwnd, color):
    """
    Stel de titelbalkkleur in naar donker thema
    """
    try:
        # Zet dark mode aan
        value = ctypes.c_int(1)  # 1 = dark mode
        dwmapi.DwmSetWindowAttribute(
            hwnd,
            DWMWA_USE_IMMERSIVE_DARK_MODE,
            ctypes.byref(value),
            ctypes.sizeof(value)
        )
    except Exception as e:
        print(f"Error setting title bar color: {e}")

class ScreenRecorder(QThread):
    recording_started = pyqtSignal()
    recording_stopped = pyqtSignal(str)  # Signaal met pad naar opgeslagen bestand
    window_changed = pyqtSignal()  # Nieuw signaal voor window verandering
    buffer_status_changed = pyqtSignal(float)  # Nieuw signaal voor buffer status (percentage)
    
    def __init__(self, save_dir, buffer_seconds=5, post_trigger_seconds=15, quality="Normal (1080p)", fps="30", pilot_name="", unit_name=""):
        super().__init__()
        self.save_dir = save_dir
        self.buffer_seconds = max(1, int(buffer_seconds))
        self.post_trigger_seconds = max(1, int(post_trigger_seconds))
        self.quality = quality
        self.fps = min(60, max(1, int(fps)))
        self.pilot_name = pilot_name
        self.unit_name = unit_name
        self.recording = False
        self.triggered = False
        self.stop_requested = False
        self.stop_time = None
        self.window_rect = None
        self.current_window_handle = None
        self.frame_buffer = []
        self.frame_times = []
        self.target_fps = float(self.fps)
        self.frame_interval = 1.0 / self.target_fps
        self.last_frame_time = time.time()
        self.last_buffer_update = time.time()
        self.font = cv2.FONT_HERSHEY_SIMPLEX
        self.last_window_rect = None
        self.out = None
        self.current_filepath = None
        self.max_buffer_frames = int(self.buffer_seconds * self.target_fps)
        self.min_sleep_time = min(0.001, self.frame_interval / 4)
        self.frame_count = 0
        self.buffer_lock = False  # Add lock for buffer operations
        
    def get_output_resolution(self, frame):
        """Bepaal de output resolutie op basis van kwaliteitsinstelling"""
        h, w = frame.shape[:2]
        
        if self.quality == "Very High (4K)":
            target_height = 2160  # 4K
            target_width = int((w / h) * target_height)
            target_width = (target_width // 2) * 2  # Zorg voor even getallen
            return (target_width, target_height)
            
        elif self.quality == "High (2K)":
            target_height = 1440  # 2K
            target_width = int((w / h) * target_height)
            target_width = (target_width // 2) * 2
            return (target_width, target_height)
            
        elif self.quality == "Normal (1080p)":
            target_height = 1080  # Full HD
            target_width = int((w / h) * target_height)
            target_width = (target_width // 2) * 2
            return (target_width, target_height)
            
        else:  # "Low (Same as window)"
            return (w, h)

    def resize_frame(self, frame):
        """Pas frame grootte aan op basis van kwaliteitsinstelling"""
        if self.quality == "Low (Same as window)":
            return frame
            
        target_size = self.get_output_resolution(frame)
        return cv2.resize(frame, target_size, interpolation=cv2.INTER_LANCZOS4)
        
    def add_recording_overlay(self, frame):
        """Voeg opname indicator en tijd/datum toe aan frame"""
        height, width = frame.shape[:2]
        
        # Huidige datum en tijd
        current_time = datetime.now()
        pilot_str = f"Pilot: {self.pilot_name}"
        unit_str = f"Unit: {self.unit_name}"
        date_str = f"Date: {current_time.strftime('%d.%m.%Y')}"
        time_str = f"Time: {current_time.strftime('%H:%M:%S')}"
        
        # Tekst instellingen
        font_scale = 1.365   # 50% groter voor alle tekst
        thickness = 2
        text_color = (255, 255, 255)  # Wit
        bg_color = (0, 0, 0)          # Zwart
        
        # Bereken tekst groottes voor achtergrond
        (pilot_w, pilot_h), _ = cv2.getTextSize(pilot_str, self.font, font_scale, thickness)
        (unit_w, unit_h), _ = cv2.getTextSize(unit_str, self.font, font_scale, thickness)
        (date_w, date_h), _ = cv2.getTextSize(date_str, self.font, font_scale, thickness)
        (time_w, time_h), _ = cv2.getTextSize(time_str, self.font, font_scale, thickness)
        
        # Posities voor tekst (links onder)
        padding = 5
        line_spacing = 15  # Extra ruimte tussen regels
        
        # Bereken posities van onder naar boven
        date_pos = (padding, height - padding)
        time_pos = (padding, date_pos[1] - time_h - line_spacing)
        unit_pos = (padding, time_pos[1] - unit_h - line_spacing)
        pilot_pos = (padding, unit_pos[1] - pilot_h - line_spacing)
        
        # Teken tekst achtergrond
        bg_height = pilot_h + unit_h + date_h + time_h + padding * 5 + line_spacing * 3
        cv2.rectangle(frame, 
                     (pilot_pos[0] - padding, pilot_pos[1] - pilot_h - padding),
                     (date_pos[0] + max(pilot_w, unit_w, time_w, date_w) + padding, date_pos[1] + padding),
                     bg_color, -1)
        
        # Teken tekst
        cv2.putText(frame, pilot_str, pilot_pos, self.font, font_scale, text_color, thickness)
        cv2.putText(frame, unit_str, unit_pos, self.font, font_scale, text_color, thickness)
        cv2.putText(frame, time_str, time_pos, self.font, font_scale, text_color, thickness)
        cv2.putText(frame, date_str, date_pos, self.font, font_scale, text_color, thickness)
        
        # Als we aan het opnemen zijn, teken rode indicator onder de balk
        if self.triggered:
            # Onder de zwarte balk
            dot_y = date_pos[1] + padding + 20
            cv2.circle(frame, (pilot_pos[0], dot_y), 10, (0, 0, 0), -1)  # Zwarte outline
            cv2.circle(frame, (pilot_pos[0], dot_y), 8, (0, 0, 255), -1)  # Rode cirkel
        
        return frame
        
    def get_active_window_rect(self):
        """Krijg de afmetingen en positie van het actieve venster, inclusief randen en titelbalk"""
        try:
            window = win32gui.GetForegroundWindow()
            if not window:
                return self.window_rect  # Return last known window rect instead of None
                
            # Haal venster informatie op
            window_rect = list(win32gui.GetWindowRect(window))
            
            # Haal de stijl van het venster op om te controleren op gemaximaliseerd/volledig scherm
            style = win32gui.GetWindowLong(window, win32con.GWL_STYLE)
            
            # Check of het venster gemaximaliseerd of in volledig scherm is
            if style & win32con.WS_MAXIMIZE:
                # Voor gemaximaliseerde vensters, gebruik het volledige scherm
                monitor = win32api.MonitorFromWindow(window)
                monitor_info = win32api.GetMonitorInfo(monitor)
                work_area = monitor_info['Work']
                window_rect = list(work_area)
            
            title = win32gui.GetWindowText(window)
            
            # Controleer of het venster minimaal formaat heeft
            if window_rect[2] - window_rect[0] <= 0 or window_rect[3] - window_rect[1] <= 0:
                return self.window_rect  # Return last known window rect
                
            # Converteer naar dict voor makkelijke vergelijking
            window_info = {
                'left': window_rect[0],
                'top': window_rect[1],
                'width': window_rect[2] - window_rect[0],
                'height': window_rect[3] - window_rect[1],
                'title': title,
                'base_title': self.get_base_window_title(title)
            }
            
            # Check voor verandering in positie of grootte
            if self.last_window_rect:
                # Alleen significante veranderingen detecteren
                # Negeer kleine veranderingen en focus changes binnen hetzelfde venster
                is_same_window = (
                    self.get_base_window_title(window_info['title']) == self.get_base_window_title(self.last_window_rect['title']) and
                    abs(window_info['width'] - self.last_window_rect['width']) < 50 and
                    abs(window_info['height'] - self.last_window_rect['height']) < 50 and
                    abs(window_info['left'] - self.last_window_rect['left']) < 200 and
                    abs(window_info['top'] - self.last_window_rect['top']) < 200
                )
                
                if is_same_window:
                    # Update positie zonder buffer te resetten
                    self.last_window_rect.update(window_info)
                    return {
                        'left': window_rect[0],
                        'top': window_rect[1],
                        'width': window_rect[2] - window_rect[0],
                        'height': window_rect[3] - window_rect[1]
                    }
                
                # Alleen echte venster veranderingen detecteren (andere applicatie)
                significant_change = (
                    abs(window_info['width'] - self.last_window_rect['width']) > 50 or
                    abs(window_info['height'] - self.last_window_rect['height']) > 50 or
                    abs(window_info['left'] - self.last_window_rect['left']) > 200 or
                    abs(window_info['top'] - self.last_window_rect['top']) > 200 or
                    self.get_base_window_title(window_info['title']) != self.get_base_window_title(self.last_window_rect['title'])
                )
                
                if significant_change:
                    print(f"Significante venster verandering gedetecteerd")
                    print(f"Van: {self.last_window_rect['title']}")
                    print(f"Naar: {window_info['title']}")
                    print(f"Nieuwe afmetingen: {window_info['width']}x{window_info['height']}")
                    
                    # Als we aan het opnemen zijn, negeer de verandering
                    if self.triggered:
                        return self.window_rect
                    
                    # Reset buffer bij echte venster wissel
                    self.clear_buffer()
                    self.last_window_rect = window_info
                    self.window_changed.emit()
                    
                    # Return nieuwe window rect
                    return {
                        'left': window_rect[0],
                        'top': window_rect[1],
                        'width': window_rect[2] - window_rect[0],
                        'height': window_rect[3] - window_rect[1]
                    }
            else:
                # Eerste keer, sla venster info op
                print(f"Eerste venster gedetecteerd: {title}")
                print(f"Positie: ({window_info['left']}, {window_info['top']})")
                print(f"Grootte: {window_info['width']}x{window_info['height']}")
                self.last_window_rect = window_info
                self.window_changed.emit()
            
            # Return het rect in het formaat dat mss.grab verwacht
            return {
                'left': window_rect[0],
                'top': window_rect[1],
                'width': window_rect[2] - window_rect[0],
                'height': window_rect[3] - window_rect[1]
            }
            
        except Exception as e:
            print(f"Error bij venster detectie: {str(e)}")
            return self.window_rect  # Return last known window rect

    def get_base_window_title(self, title):
        """Extraheert de basis applicatie naam uit een venstertitel"""
        # Bekende patronen voor verschillende applicaties
        if " - File Explorer" in title:
            return "File Explorer"
        if " - Google Chrome" in title:
            return "Google Chrome"
        if " - Microsoft Edge" in title:
            return "Microsoft Edge"
        if " - Visual Studio Code" in title:
            return "Visual Studio Code"
        if " - Notepad" in title:
            return "Notepad"
        
        # Voor andere applicaties, probeer het eerste deel van de titel te gebruiken
        # tot aan een scheidingsteken zoals ' - ', ' | ', etc.
        for separator in [' - ', ' | ', ' — ', ' – ']:
            if separator in title:
                parts = title.split(separator)
                # Neem het laatste deel als het waarschijnlijk de app naam is
                if len(parts[-1].strip()) < len(parts[0].strip()):
                    return parts[-1].strip()
                # Anders neem het eerste deel
                return parts[0].strip()
        
        # Als geen scheidingsteken gevonden, return de hele titel
        return title.strip()

    def manage_buffer(self, frame, current_time):
        """Manage the frame buffer with proper error handling"""
        try:
            if frame is None or self.buffer_lock:
                return
                
            # Calculate max buffer size based on FPS and buffer seconds
            max_frames = int(float(self.fps) * self.buffer_seconds)
            
            # Add new frame to buffer with timestamp
            frame_copy = frame.copy()
            
            # Calculate minimum time between frames based on FPS
            min_frame_interval = 1.0 / float(self.fps)
            
            # Only add frame if enough time has passed since last frame
            if not self.frame_times or (current_time - self.frame_times[-1]) >= min_frame_interval * 0.9:
                self.frame_buffer.append(frame_copy)
                self.frame_times.append(current_time)
                self.frame_count += 1
                
                # Remove old frames while checking buffer size
                while len(self.frame_buffer) > max_frames:
                    if self.frame_buffer and self.frame_times:
                        self.frame_buffer.pop(0)
                        self.frame_times.pop(0)
                        self.frame_count = len(self.frame_buffer)
                
                # Update buffer status with proper interval
                if current_time - self.last_buffer_update >= 0.1:
                    if self.frame_times and len(self.frame_times) > 1:
                        # Calculate buffer percentage based on actual recorded time
                        buffer_duration = self.frame_times[-1] - self.frame_times[0]
                        buffer_percentage = min((buffer_duration / self.buffer_seconds) * 100, 100)
                        
                        # Calculate actual FPS based on frame count and duration
                        elapsed_time = buffer_duration if buffer_duration > 0 else 0.001
                        current_fps = self.frame_count / elapsed_time if elapsed_time > 0 else 0
                        
                        # Only print status if buffer has meaningful content and not locked
                        if self.frame_count > 0 and not self.buffer_lock:
                            print(f"Pre-trigger status: {buffer_percentage:.1f}%, {self.frame_count} frames over {elapsed_time:.1f} sec ({current_fps:.1f} fps)")
                        
                        self.buffer_status_changed.emit(buffer_percentage)
                        self.last_buffer_update = current_time
                
        except Exception as e:
            print(f"Error in buffer management: {str(e)}")
            import traceback
            traceback.print_exc()

    def clear_buffer(self):
        """Safely clear the buffer"""
        try:
            self.buffer_lock = True  # Lock buffer operations
            self.frame_buffer.clear()
            self.frame_times.clear()
            self.frame_count = 0
            self.last_frame_time = time.time()
            self.last_buffer_update = time.time()
            self.buffer_status_changed.emit(0)
            print("Buffer cleared")
            self.buffer_lock = False  # Release lock
        except Exception as e:
            print(f"Error clearing buffer: {str(e)}")
            self.buffer_lock = False  # Ensure lock is released
            import traceback
            traceback.print_exc()

    def get_buffer_percentage(self):
        """Calculate buffer fill percentage safely"""
        try:
            if not self.frame_times or len(self.frame_times) < 2:
                return 0
            buffer_time = self.frame_times[-1] - self.frame_times[0]
            return min((buffer_time / self.buffer_seconds) * 100, 100)
        except Exception as e:
            print(f"Error calculating buffer percentage: {str(e)}")
            return 0
            
    def extend_recording(self):
        """Verleng de opname met post_trigger_seconds"""
        if self.triggered:
            print(f"Extending recording by {self.post_trigger_seconds} seconds")
            self.stop_time = time.time() + self.post_trigger_seconds
            print(f"New stop time: {datetime.fromtimestamp(self.stop_time).strftime('%H:%M:%S')}")
            
    def run(self):
        try:
            print(f"Start recording setup...")
            print(f"Save directory: {self.save_dir}")
            print(f"Pre-trigger size: {self.buffer_seconds}s at {self.fps} FPS")
            
            with mss.mss() as self.sct:
                self.recording = True
                self.last_frame_time = time.time()
                last_window_check = time.time()
                window_check_interval = 0.1
                frame_interval = 1.0 / float(self.fps)
                min_sleep = min(0.001, frame_interval / 4)
                
                while self.recording:
                    try:
                        current_time = time.time()
                        frame_delta = current_time - self.last_frame_time
                        
                        # Check window with interval
                        if current_time - last_window_check >= window_check_interval:
                            new_window_rect = self.get_active_window_rect()
                            last_window_check = current_time
                            
                            if new_window_rect:
                                if self.window_rect != new_window_rect:
                                    self.window_rect = new_window_rect
                                    if not self.triggered:
                                        self.clear_buffer()
                                        print("Window changed, buffer reset")
                            
                            if not self.window_rect:
                                time.sleep(min_sleep)
                                continue
                        
                        # Wait for next frame timing
                        if frame_delta < frame_interval:
                            sleep_time = max(min_sleep, (frame_interval - frame_delta) * 0.8)
                            time.sleep(sleep_time)
                            continue
                        
                        # Capture and process frame
                        if not self.window_rect:
                            time.sleep(min_sleep)
                            continue
                            
                        screenshot = self.sct.grab(self.window_rect)
                        if screenshot is None:
                            continue
                            
                        frame = np.array(screenshot)
                        if frame is None or frame.size == 0:
                            continue
                            
                        frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2BGR)
                        
                        # Resize frame according to quality setting
                        frame = self.resize_frame(frame)
                        
                        # Add overlay after resizing
                        frame = self.add_recording_overlay(frame)
                        
                        # Manage buffer or write frame
                        if not self.triggered:
                            self.manage_buffer(frame, current_time)
                        elif self.out:
                            # Ensure we're writing frames at the correct rate
                            if frame_delta >= frame_interval:
                                self.out.write(frame)
                                self.last_frame_time = current_time
                        
                    except Exception as e:
                        print(f"Error in main loop: {str(e)}")
                        time.sleep(min_sleep)
                        continue
                
                # Cleanup
                self.cleanup()
                
        except Exception as e:
            print(f"Fatal error in recording thread: {str(e)}")
            import traceback
            traceback.print_exc()
            self.recording = False
            
    def start_new_recording(self):
        """Start een nieuwe opname met de huidige buffer"""
        try:
            # Genereer bestandsnaam met timestamp
            timestamp = datetime.now().strftime("%d.%m.%Y")
            filename = f"GunCam_{datetime.now().strftime('%H.%M')}.mp4"
            self.current_filepath = os.path.join(self.save_dir, timestamp, filename)
            
            # Maak directory aan als deze niet bestaat
            os.makedirs(os.path.dirname(self.current_filepath), exist_ok=True)
            
            # Bepaal de juiste resolutie voor de opname
            if not self.window_rect:
                raise Exception("Geen venster gedetecteerd")
                
            # Bereken de juiste resolutie op basis van kwaliteitsinstelling
            target_size = self.get_output_resolution(np.zeros((self.window_rect['height'], self.window_rect['width'], 3)))
            print(f"Opname resolutie: {target_size[0]}x{target_size[1]}")
            
            # Test verschillende codecs met verschillende extensies
            codecs = [
                ('mp4v', '.mp4'),
                ('XVID', '.avi'),
                ('MJPG', '.avi'),
                ('avc1', '.mp4'),
                ('H264', '.mp4')
            ]
            
            working_codec = None
            working_ext = None
            for codec, ext in codecs:
                try:
                    # Test de codec met een tijdelijke bestandsnaam
                    test_file = self.current_filepath.replace('.mp4', ext)
                    test_out = cv2.VideoWriter(
                        test_file,
                        cv2.VideoWriter_fourcc(*codec),
                        float(self.fps),
                        (target_size[0], target_size[1])
                    )
                    if test_out.isOpened():
                        test_out.release()
                        working_codec = codec
                        working_ext = ext
                        self.current_filepath = test_file
                        print(f"Codec {codec} werkt met extensie {ext}")
                        break
                except Exception as e:
                    print(f"Codec {codec} niet beschikbaar: {str(e)}")
                    continue
            
            if not working_codec:
                raise Exception("Geen werkende codec gevonden")
            
            print(f"Succesvol gestart met codec: {working_codec}")
            
            # Start de opname met de juiste resolutie
            self.out = cv2.VideoWriter(
                self.current_filepath,
                cv2.VideoWriter_fourcc(*working_codec),
                float(self.fps),
                (target_size[0], target_size[1])
            )
            
            if not self.out.isOpened():
                raise Exception("Kon video writer niet openen")
            
            # Schrijf de buffer met de juiste resolutie
            print(f"Buffer schrijven: {len(self.frame_buffer)} frames")
            for frame in self.frame_buffer:
                self.out.write(frame)  # Buffer frames zijn al geresized
            print("Buffer succesvol geschreven")
            
            # Start de opname en stel stop tijd in
            self.triggered = True
            self.stop_time = time.time() + self.post_trigger_seconds
            self.recording_started.emit()
            print(f"Recording started... Will stop at {datetime.fromtimestamp(self.stop_time).strftime('%H:%M:%S')}")
            
        except Exception as e:
            error_msg = f"Error bij starten opname: {str(e)}"
            print(error_msg)
            self.recording_stopped.emit(error_msg)
            self.triggered = False
            if self.out:
                self.out.release()
                self.out = None

    def cleanup(self):
        """Clean up resources"""
        if self.out:
            try:
                self.out.release()
                if self.current_filepath:
                    self.recording_stopped.emit(self.current_filepath)
            except Exception as e:
                print(f"Error during cleanup: {str(e)}")
            finally:
                self.out = None
                self.current_filepath = None

    def stop(self):
        """Stop de opname en cleanup resources"""
        try:
            print("Stopping recording...")
            if self.out:
                self.out.release()
                self.out = None
            print("Video writer released")
            
            if self.current_filepath:
                print(f"Recording saved to: {self.current_filepath}")
                self.recording_stopped.emit(self.current_filepath)
                self.current_filepath = None
            
            self.triggered = False
            print("Recording stopped")
            
        except Exception as e:
            print(f"Error stopping recording: {str(e)}")
            import traceback
            traceback.print_exc()
            
    def on_trigger_state_changed(self, is_pressed):
        """Handle trigger button state changes"""
        self.update_button_color(is_pressed)
        
        if is_pressed:
            # Start or extend recording
            if self.screen_recorder:
                if not self.screen_recorder.triggered:
                    # Start new recording
                    self.countdown_timer.stop()
                    total_recording_time = self.post_trigger_spinbox.value()
                    self.countdown_seconds = total_recording_time
                    self.recording_indicator.setMaximum(total_recording_time)
                    self.recording_indicator.setValue(total_recording_time)
                    self.screen_recorder.start_new_recording()
                    self.status_label.setText(f"Recording started ({self.buffer_spinbox.value()}+{total_recording_time}s total)...")
                else:
                    # Reset countdown timer
                    self.countdown_timer.stop()
                    total_recording_time = self.post_trigger_spinbox.value()
                    self.countdown_seconds = total_recording_time
                    self.recording_indicator.setMaximum(total_recording_time)
                    self.recording_indicator.setValue(total_recording_time)
                    self.screen_recorder.extend_recording()
                    self.status_label.setText(f"Recording extended ({total_recording_time}s from trigger)...")
        else:
            # Start countdown to stop recording
            if self.screen_recorder and self.screen_recorder.triggered:
                self.countdown_timer.start(1000)  # Update every second
                self.status_label.setText(f"Recording stops in {self.countdown_seconds} seconds...")

    def update_countdown(self):
        """Update the countdown timer and stop recording when it reaches zero"""
        if not self.screen_recorder or not self.screen_recorder.triggered:
            self.countdown_timer.stop()
            self.recording_indicator.setValue(0)
            self.status_label.setText("Pre-trigger active...")
            return
            
        self.countdown_seconds -= 1
        self.recording_indicator.setValue(self.countdown_seconds)
        
        if self.countdown_seconds > 0:
            self.status_label.setText(f"Recording stops in {self.countdown_seconds} seconds... ({self.countdown_seconds}s total)")
        else:
            self.countdown_timer.stop()
            self.countdown_seconds = self.buffer_spinbox.value() + self.post_trigger_spinbox.value()
            self.recording_indicator.setValue(0)
            if self.screen_recorder:
                self.screen_recorder.stop()
                self.status_label.setText("Recording stopped, pre-trigger active...")

    def on_recording_started(self):
        print("Recording started...")
        total_recording_time = self.buffer_spinbox.value() + self.post_trigger_spinbox.value()
        self.status_label.setText(f"Recording active ({total_recording_time}s total)...")
        self.recording_indicator.setValue(total_recording_time)

    def on_recording_stopped(self, filepath):
        print(f"Recording saved: {filepath}")
        self.status_label.setText(f"Recording saved: {os.path.basename(filepath)}")
        self.recording_indicator.setValue(0)
        self.update_files_list()
        
        # Start new buffer
        self.start_buffer()
        
        # Reset countdown with total time
        self.countdown_timer.stop()
        self.countdown_seconds = self.buffer_spinbox.value() + self.post_trigger_spinbox.value()

    def start_listening(self, trigger_number):
        try:
            # Ensure pygame is initialized
            if not pygame.get_init():
                pygame.init()
            if not pygame.joystick.get_init():
                pygame.joystick.init()
            
            # Stop existing threads
            self.stop_all_threads()
            
            joystick_count = pygame.joystick.get_count()
            if joystick_count == 0:
                QMessageBox.warning(self, "Error", "No joysticks found!")
                self.get_trigger_button(trigger_number).setEnabled(True)
                return
            
            # Test each joystick
            print("\nDetected joysticks:")
            for i in range(joystick_count):
                try:
                    joy = pygame.joystick.Joystick(i)
                    joy.init()
                    print(f"Joystick {i}: {joy.get_name()} - {joy.get_numbuttons()} buttons")
                    joy.quit()  # Release for thread usage
                except pygame.error as e:
                    print(f"Error initializing joystick {i}: {e}")
                    continue
            
            self.get_trigger_button(trigger_number).setText("Press a button...")
            self.get_trigger_button(trigger_number).setEnabled(False)
            
            # Start threads for all joysticks
            for i in range(joystick_count):
                thread = JoystickThread(i)
                thread.button_pressed.connect(lambda b, n, id, tn=trigger_number: self.on_button_pressed(b, n, id, tn))
                thread.start()
                self.joystick_threads.append(thread)
        except Exception as e:
            print(f"Error in start_listening: {e}")
            QMessageBox.warning(self, "Error", f"Failed to initialize joysticks: {str(e)}")
            self.get_trigger_button(trigger_number).setEnabled(True)

    def stop_all_threads(self):
        # Stop joystick threads
        for thread in self.joystick_threads:
            thread.stop()
            thread.wait()
        self.joystick_threads.clear()
        
        # Stop button monitor thread
        if hasattr(self, 'button_monitor') and self.button_monitor:
            self.button_monitor.stop()
            self.button_monitor.wait()
            self.button_monitor = None

    def on_button_pressed(self, button, joystick_name, joystick_id, trigger_number):
        # Update trigger button text immediately
        self.get_trigger_button(trigger_number).setText(f"Setting up: Button {button} on {joystick_name}")
        
        # Wait 2 seconds before setting the trigger
        QTimer.singleShot(2000, lambda: self.finish_button_setup(button, joystick_name, joystick_id, trigger_number))

    def finish_button_setup(self, button, joystick_name, joystick_id, trigger_number):
        settings = self.config['Settings']
        settings[f'trigger_button_{trigger_number}'] = str(button)
        settings[f'joystick_name_{trigger_number}'] = joystick_name
        settings[f'joystick_id_{trigger_number}'] = str(joystick_id)
        self.save_config()
        
        # Update trigger button text with just the button number
        self.get_trigger_button(trigger_number).setText(f"Button {button}")
        self.get_trigger_button(trigger_number).setEnabled(True)
        self.stop_all_threads()
        
        # Start monitoring the new trigger button
        self.start_button_monitors()
        
        # Restart the buffer
        self.start_buffer()

    def open_storage_folder(self):
        settings = self.config['Settings']
        folder_path = settings.get('video_path', '')
        if os.path.exists(folder_path):
            # Open de map in de standaard bestandsverkenner
            if os.name == 'nt':  # Windows
                os.startfile(folder_path)
            else:  # Linux/Mac
                import subprocess
                subprocess.Popen(['xdg-open', folder_path])
        else:
            QMessageBox.warning(self, "Fout", f"Map bestaat niet: {folder_path}")

    def closeEvent(self, event):
        """Stop de background timer bij het sluiten van de applicatie"""
        print("Closing application...")
        self.background_timer.stop()
        self.save_config()
        self.stop_all_threads()
        if hasattr(self, 'screen_recorder'):
            self.screen_recorder.stop()
        pygame.quit()
        event.accept()

    def update_files_list(self):
        settings = self.config['Settings']
        folder_path = settings.get('video_path', '')
        if os.path.exists(folder_path):
            # Find all mp4 files recursively (including subfolders)
            files_text = "Recent recordings:\n"
            found_files = []
            
            for root, dirs, files in os.walk(folder_path):
                for f in files:
                    if f.endswith('.mp4'):
                        full_path = os.path.join(root, f)
                        rel_path = os.path.relpath(full_path, folder_path)
                        mod_time = datetime.fromtimestamp(os.path.getmtime(full_path))
                        size_mb = os.path.getsize(full_path) / (1024 * 1024)
                        found_files.append((full_path, rel_path, mod_time, size_mb))
            
            # Sort by date (newest first) and show last 5
            found_files.sort(key=lambda x: x[2], reverse=True)
            if found_files:
                for _, rel_path, mod_time, size_mb in found_files[:5]:
                    files_text += f"{rel_path}\n"
                    files_text += f"  {mod_time.strftime('%H:%M')} ({size_mb:.1f} MB)\n"
            else:
                files_text = "No recordings found"
            
            self.files_label.setText(files_text)
        else:
            self.files_label.setText("Folder does not exist")

    def start_buffer(self):
        """Start the pre-trigger recording"""
        if not self.screen_recorder or not self.screen_recorder.recording:
            # Get settings from config
            settings = self.config['Settings']
            
            # Create new recorder with current settings
            self.screen_recorder = ScreenRecorder(
                settings['video_path'],
                buffer_seconds=int(settings['buffer_seconds']),
                post_trigger_seconds=int(settings['post_trigger_seconds']),
                quality=settings['quality'],
                fps=settings['fps'],
                pilot_name=settings['pilot_name'],
                unit_name=settings['unit_name']
            )
            
            # Connect signals
            self.screen_recorder.recording_started.connect(self.on_recording_started)
            self.screen_recorder.recording_stopped.connect(self.on_recording_stopped)
            self.screen_recorder.window_changed.connect(self.on_window_changed)
            self.screen_recorder.buffer_status_changed.connect(self.update_buffer_indicator)
            
            # Start the recorder
            self.screen_recorder.start()
            self.status_label.setText("Pre-trigger active...")

    def on_window_changed(self):
        """Handler for window change"""
        if not self.screen_recorder or not self.screen_recorder.triggered:
            self.status_label.setText("Window changed, rebuilding pre-trigger...")
            self.buffer_indicator.setValue(0)  # Reset buffer indicator
            
            # Reset de buffer status na een korte vertraging
            def update_status():
                if self.screen_recorder and not self.screen_recorder.triggered:
                    self.status_label.setText("Pre-trigger active...")
            
            QTimer.singleShot(3000, update_status)  # Verhoogd van 2000 naar 3000ms

    def update_buffer_indicator(self, percentage):
        """Update the buffer indicator with percentage and color"""
        # Ensure percentage is between 0 and 100
        percentage = max(0, min(100, percentage))
        self.buffer_indicator.setValue(int(percentage))
        
        # Calculate color based on percentage (red -> yellow -> green)
        if percentage < 50:
            # Red to yellow (0-50%)
            r = 255
            g = int((percentage / 50) * 255)  # Linear interpolation from 0 to 255
            b = 0
        else:
            # Yellow to green (50-100%)
            r = int(255 - ((percentage - 50) / 50) * 255)  # Linear interpolation from 255 to 0
            g = 255  # Keep green at maximum
            b = 0
            
        # Convert to hex color code
        color = f"#{r:02x}{g:02x}{b:02x}"
            
        self.buffer_indicator.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid #3d3d3d;
                border-radius: 2px;
                text-align: center;
                background-color: rgba(30, 30, 30, 150);
                min-height: 20px;
                max-height: 20px;
            }}
            QProgressBar::chunk {{
                background-color: {color};
            }}
        """)

    def on_settings_changed(self):
        """Handler for when settings are changed"""
        try:
            # Save new values in config
            settings = self.config['Settings']
            settings['buffer_seconds'] = str(self.buffer_spinbox.value())
            settings['post_trigger_seconds'] = str(self.post_trigger_spinbox.value())
            settings['fps'] = self.fps_combo.currentText()
            settings['quality'] = self.quality_combo.currentText()
            
            # Only update pilot name and unit name if they are not empty
            pilot_name = self.pilot_input.text()
            if pilot_name:
                settings['pilot_name'] = pilot_name
                
            unit_name = self.unit_input.text()
            if unit_name:
                settings['unit_name'] = unit_name
            
            # Save to config file immediately
            config_path = os.path.join(os.path.dirname(__file__), 'settings.cfg')
            with open(config_path, 'w') as configfile:
                self.config.write(configfile)
            
            print(f"Settings changed:")
            print(f"- Pre-trigger duration: {self.buffer_spinbox.value()} seconds")
            print(f"- Post-trigger duration: {self.post_trigger_spinbox.value()} seconds")
            print(f"- Recording quality: {self.quality_combo.currentText()}")
            print(f"- FPS: {self.fps_combo.currentText()}")
            print(f"- Pilot Name: {pilot_name}")
            print(f"- Flight Unit: {unit_name}")
            
            # Update recorder settings if it exists
            if self.screen_recorder:
                # Store triggered state
                old_triggered = self.screen_recorder.triggered
                
                # Update settings safely
                self.screen_recorder.update_settings(
                    self.buffer_spinbox.value(),
                    self.post_trigger_spinbox.value(),
                    self.fps_combo.currentText(),
                    self.pilot_input.text(),
                    self.unit_input.text()
                )
                
                # Restore triggered state if needed
                if old_triggered:
                    self.screen_recorder.triggered = True
                
                self.status_label.setText("Settings updated, pre-trigger active...")
                
        except Exception as e:
            print(f"Error updating settings: {str(e)}")
            self.status_label.setText("Error updating settings")

    def open_website(self, url):
        """Open een website in de standaard browser"""
        import webbrowser
        webbrowser.open(url)

    def rotate_background(self):
        """Wissel naar de volgende achtergrondafbeelding"""
        self.current_background = (self.current_background % 4) + 1  # Aangepast van 3 naar 4
        self.load_current_background()
        
    def load_current_background(self):
        """Laad de huidige achtergrondafbeelding"""
        try:
            bg_path = os.path.join(os.path.dirname(__file__), f"Images/guncam_bg_source_{self.current_background}.jpg")
            if os.path.exists(bg_path):
                # Laad de originele afbeelding
                background = QPixmap(bg_path)
                
                # Bereken de juiste schaling om de hele window te vullen
                window_ratio = 900 / 700  # window breedte / hoogte
                image_ratio = background.width() / background.height()
                
                if image_ratio > window_ratio:
                    # Afbeelding is relatief breder dan window, schaal op hoogte
                    scaled_height = 700
                    scaled_width = int(700 * image_ratio)
                else:
                    # Afbeelding is relatief hoger dan window, schaal op breedte
                    scaled_width = 900
                    scaled_height = int(900 / image_ratio)
                
                # Schaal de afbeelding
                scaled_bg = background.scaled(scaled_width, scaled_height, 
                                           Qt.AspectRatioMode.KeepAspectRatio,
                                           Qt.TransformationMode.SmoothTransformation)
                
                # Bereken het uitsnede gebied om te centreren
                x = max(0, (scaled_width - 900) // 2)
                y = max(0, (scaled_height - 700) // 2)
                
                # Knip de afbeelding bij naar window formaat
                cropped_bg = scaled_bg.copy(x, y, 900, 700)
                
                # Stel de uitgesneden en geschaalde afbeelding in
                self.background_label.setPixmap(cropped_bg)
            else:
                print(f"Warning: Background image not found: {bg_path}")
        except Exception as e:
            print(f"Error loading background: {str(e)}")

    def on_trigger_state_changed(self, is_pressed):
        """Handle trigger button state changes"""
        self.update_button_color(is_pressed)
        
        if is_pressed:
            # Start or extend recording
            if self.screen_recorder:
                if not self.screen_recorder.triggered:
                    # Start new recording
                    self.countdown_timer.stop()
                    total_recording_time = self.post_trigger_spinbox.value()
                    self.countdown_seconds = total_recording_time
                    self.recording_indicator.setMaximum(total_recording_time)
                    self.recording_indicator.setValue(total_recording_time)
                    self.screen_recorder.start_new_recording()
                    self.status_label.setText(f"Recording started ({self.buffer_spinbox.value()}+{total_recording_time}s total)...")
                else:
                    # Reset countdown timer
                    self.countdown_timer.stop()
                    total_recording_time = self.post_trigger_spinbox.value()
                    self.countdown_seconds = total_recording_time
                    self.recording_indicator.setMaximum(total_recording_time)
                    self.recording_indicator.setValue(total_recording_time)
                    self.screen_recorder.extend_recording()
                    self.status_label.setText(f"Recording extended ({total_recording_time}s from trigger)...")
        else:
            # Start countdown to stop recording
            if self.screen_recorder and self.screen_recorder.triggered:
                self.countdown_timer.start(1000)  # Update every second
                self.status_label.setText(f"Recording stops in {self.countdown_seconds} seconds...")

    def update_settings(self, buffer_seconds, post_trigger_seconds, fps, pilot_name="", unit_name=""):
        """Update recorder settings safely"""
        try:
            self.buffer_seconds = max(1, int(buffer_seconds))
            self.post_trigger_seconds = max(1, int(post_trigger_seconds))
            self.fps = min(60, max(1, int(fps)))
            self.pilot_name = pilot_name
            self.unit_name = unit_name
            self.max_buffer_frames = int(self.buffer_seconds * float(self.fps))
            print(f"Settings updated: {self.buffer_seconds}s buffer, {self.post_trigger_seconds}s post-trigger, {self.fps} FPS")
            print(f"Pilot: {self.pilot_name}, Unit: {self.unit_name}")
            return True
        except Exception as e:
            print(f"Error updating settings: {str(e)}")
            return False

class ButtonMonitorThread(QThread):
    button_state_changed = pyqtSignal(bool)  # True als ingedrukt, False als losgelaten

    def __init__(self, button, joystick_id, parent=None):
        super().__init__(parent)
        self.button = button
        self.joystick_id = joystick_id
        self.running = True
        self.joy = None
        self.last_state = False
        try:
            self.joy = pygame.joystick.Joystick(joystick_id)
            self.joy.init()
        except pygame.error:
            print(f"Could not initialize joystick {joystick_id}")

    def run(self):
        if not self.joy:
            return

        while self.running:
            try:
                pygame.event.pump()
                current_state = self.joy.get_button(self.button)
                
                # Alleen emit als de staat verandert
                if current_state != self.last_state:
                    self.button_state_changed.emit(current_state)
                    self.last_state = current_state
                    
                time.sleep(0.1)  # Reduce CPU usage
                
            except pygame.error as e:
                print(f"Joystick error: {e}")
                if "Joystick not initialized" in str(e):
                    # Try to reinitialize
                    try:
                        pygame.joystick.quit()
                        pygame.joystick.init()
                        self.joy = pygame.joystick.Joystick(self.joystick_id)
                        self.joy.init()
                        continue
                    except pygame.error:
                        break
                break
            except Exception as e:
                print(f"Error in button monitor thread: {e}")
                break

    def stop(self):
        self.running = False
        if self.joy:
            try:
                self.joy.quit()
            except pygame.error:
                pass

class JoystickThread(QThread):
    button_pressed = pyqtSignal(int, str, int)

    def __init__(self, joystick_id):
        super().__init__()
        self.joystick_id = joystick_id
        self.running = True
        self.joy = None
        
        # Initialize pygame in the thread
        if not pygame.get_init():
            pygame.init()
        if not pygame.joystick.get_init():
            pygame.joystick.init()
            
        try:
            self.joy = pygame.joystick.Joystick(joystick_id)
            self.joy.init()
            print(f"Initialized joystick {joystick_id}: {self.joy.get_name()}")
        except pygame.error as e:
            print(f"Could not initialize joystick {joystick_id}: {e}")

    def run(self):
        if not self.joy:
            return
            
        # Ensure pygame is initialized
        if not pygame.get_init():
            pygame.init()
        if not pygame.joystick.get_init():
            pygame.joystick.init()
            
        try:
            # Re-initialize joystick to ensure it's active
            if not self.joy.get_init():
                self.joy.init()
            last_states = [False] * self.joy.get_numbuttons()
        except pygame.error as e:
            print(f"Error initializing joystick states: {e}")
            return

        while self.running:
            try:
                pygame.event.pump()  # Process events
                
                # Check all buttons
                for i in range(self.joy.get_numbuttons()):
                    try:
                        current_state = self.joy.get_button(i)
                        if current_state and not last_states[i]:  # Button just pressed
                            print(f"Button {i} pressed on {self.joy.get_name()}")
                            self.button_pressed.emit(i, self.joy.get_name(), self.joystick_id)
                        last_states[i] = current_state
                    except pygame.error:
                        continue  # Skip this button if there's an error
                
                time.sleep(0.1)  # Reduce CPU usage
                
            except pygame.error as e:
                print(f"Joystick error: {e}")
                # Try to reinitialize
                try:
                    if not pygame.get_init():
                        pygame.init()
                    if not pygame.joystick.get_init():
                        pygame.joystick.init()
                    self.joy = pygame.joystick.Joystick(self.joystick_id)
                    self.joy.init()
                    last_states = [False] * self.joy.get_numbuttons()
                    continue
                except pygame.error:
                    break
            except Exception as e:
                print(f"Error in joystick thread: {e}")
                break

    def stop(self):
        self.running = False
        if self.joy and self.joy.get_init():
            try:
                self.joy.quit()
            except pygame.error:
                pass

class MainWindow(QMainWindow):
    def __init__(self):
        # Main window setup
        super().__init__()
        self.setWindowTitle("DCS GunCam v1.5 - SHOOT")
        self.setFixedSize(900, 700)  # Verlaagd van 800 naar 700
        
        # Set dark title bar using DWM API
        hwnd = self.winId().__int__()
        set_titlebar_color(hwnd, None)
        
        # Set custom icon
        icon_path = os.path.join(os.path.dirname(__file__), "icon.png")
        if os.path.exists(icon_path):
            self.setWindowIcon(QIcon(icon_path))
        
        # Initialize pygame at startup
        pygame.init()
        pygame.joystick.init()
        
        # Maak een central widget met een transparante achtergrond
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        
        # Maak een background label voor de afbeelding
        self.background_label = QLabel(central_widget)
        self.background_label.setGeometry(0, 0, 900, 700)  # Verlaagd van 800 naar 700
        
        # Initialiseer achtergrond rotatie
        self.current_background = 1
        self.background_timer = QTimer()
        self.background_timer.timeout.connect(self.rotate_background)
        self.background_timer.start(5000)  # Wissel elke 5 seconden
        
        # Laad de eerste achtergrondafbeelding
        self.load_current_background()
        
        # Maak een semi-transparant widget voor de controls, rechts uitgelijnd
        self.controls_widget = QWidget(central_widget)
        self.controls_widget.setGeometry(464, 140, 416, 550)  # Y positie aangepast van 52 naar 140 pixels
        
        # Update stylesheet to include white text for input fields
        self.controls_widget.setStyleSheet("""
            QWidget {
                background-color: rgba(30, 30, 30, 150);
            }
            QLabel {
                color: white;
                background-color: transparent;
            }
            QSpinBox, QComboBox, QLineEdit {
                background-color: rgba(45, 45, 45, 200);
                color: white;
                border: 1px solid #3d3d3d;
                padding: 5px;
            }
            QComboBox QAbstractItemView {
                background-color: rgba(45, 45, 45, 200);
                color: white;
                selection-background-color: rgba(60, 60, 60, 200);
            }
            QComboBox::drop-down {
                border: none;
                background-color: rgba(45, 45, 45, 200);
            }
            QComboBox::down-arrow {
                background-color: rgba(45, 45, 45, 200);
                width: 16px;
                height: 16px;
            }
            QPushButton {
                background-color: rgba(45, 45, 45, 200);
                color: white;
                border: 1px solid #3d3d3d;
                padding: 8px;
                border-radius: 4px;
            }
            QPushButton:hover {
                background-color: rgba(60, 60, 60, 200);
            }
            QProgressBar {
                border: 1px solid #3d3d3d;
                border-radius: 2px;
                text-align: center;
                background-color: rgba(30, 30, 30, 150);
                min-height: 20px;
                max-height: 20px;
            }
            QProgressBar::chunk {
                background-color: #006400;
            }
        """)
        
        # Maak een layout voor de controls
        layout = QVBoxLayout(self.controls_widget)
        layout.setContentsMargins(15, 15, 15, 15)  # Standaard margins
        layout.setSpacing(13)  # Verhoogd van 8 naar 10 voor meer ruimte tussen elementen
        
        # Trigger buttons in horizontal layout
        trigger_buttons_layout = QHBoxLayout()
        trigger_buttons_layout.setSpacing(10)  # Add spacing between buttons
        
        # Gun Trigger
        gun_trigger_layout = QVBoxLayout()
        gun_trigger_label = QLabel("Gun Trigger")
        gun_trigger_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.gun_trigger_button = QPushButton("Button 1")
        self.gun_trigger_button.clicked.connect(lambda: self.start_listening(1))
        gun_trigger_layout.addWidget(gun_trigger_label)
        gun_trigger_layout.addWidget(self.gun_trigger_button)
        trigger_buttons_layout.addLayout(gun_trigger_layout)
        
        # Canon Trigger
        canon_trigger_layout = QVBoxLayout()
        canon_trigger_label = QLabel("Canon Trigger")
        canon_trigger_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.canon_trigger_button = QPushButton("Button 2")
        self.canon_trigger_button.clicked.connect(lambda: self.start_listening(2))
        canon_trigger_layout.addWidget(canon_trigger_label)
        canon_trigger_layout.addWidget(self.canon_trigger_button)
        trigger_buttons_layout.addLayout(canon_trigger_layout)
        
        # Rockets/Bomb Trigger
        rockets_trigger_layout = QVBoxLayout()
        rockets_trigger_label = QLabel("Rockets/Bomb Trigger")
        rockets_trigger_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.rockets_trigger_button = QPushButton("Button 3")
        self.rockets_trigger_button.clicked.connect(lambda: self.start_listening(3))
        rockets_trigger_layout.addWidget(rockets_trigger_label)
        rockets_trigger_layout.addWidget(self.rockets_trigger_button)
        trigger_buttons_layout.addLayout(rockets_trigger_layout)
        
        layout.addLayout(trigger_buttons_layout)
        
        # Buffer duration
        buffer_layout = QHBoxLayout()
        buffer_label = QLabel("Pre-trigger duration (seconds):")
        buffer_label.setFixedWidth(200)
        self.buffer_spinbox = QSpinBox()
        self.buffer_spinbox.setRange(1, 60)
        self.buffer_spinbox.valueChanged.connect(self.on_settings_changed)
        self.buffer_spinbox.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        buffer_layout.addWidget(buffer_label)
        buffer_layout.addWidget(self.buffer_spinbox)
        layout.addLayout(buffer_layout)

        # Post-trigger duration
        post_trigger_layout = QHBoxLayout()
        post_trigger_label = QLabel("Post-trigger duration (seconds):")
        post_trigger_label.setFixedWidth(200)
        self.post_trigger_spinbox = QSpinBox()
        self.post_trigger_spinbox.setRange(1, 300)
        self.post_trigger_spinbox.valueChanged.connect(self.on_settings_changed)
        self.post_trigger_spinbox.setButtonSymbols(QSpinBox.ButtonSymbols.NoButtons)
        post_trigger_layout.addWidget(post_trigger_label)
        post_trigger_layout.addWidget(self.post_trigger_spinbox)
        layout.addLayout(post_trigger_layout)

        # Recording quality
        quality_layout = QHBoxLayout()
        quality_label = QLabel("Recording quality:")
        quality_label.setFixedWidth(200)
        self.quality_combo = QComboBox()
        self.quality_combo.addItems(["Very High (4K)", "High (2K)", "Normal (1080p)", "Low (Same as window)"])
        self.quality_combo.setCurrentText("Normal (1080p)")
        self.quality_combo.currentIndexChanged.connect(self.on_settings_changed)
        quality_layout.addWidget(quality_label)
        quality_layout.addWidget(self.quality_combo)
        layout.addLayout(quality_layout)

        # FPS
        fps_layout = QHBoxLayout()
        fps_label = QLabel("FPS:")
        fps_label.setFixedWidth(200)
        self.fps_combo = QComboBox()
        self.fps_combo.addItems(["30", "60"])
        self.fps_combo.setCurrentText("30")
        self.fps_combo.currentTextChanged.connect(self.on_settings_changed)
        fps_layout.addWidget(fps_label)
        fps_layout.addWidget(self.fps_combo)
        layout.addLayout(fps_layout)

        # Pilot Name
        pilot_layout = QHBoxLayout()
        pilot_label = QLabel("Pilot Name:")
        pilot_label.setFixedWidth(200)
        self.pilot_input = QLineEdit()
        self.pilot_input.textChanged.connect(self.on_settings_changed)
        pilot_layout.addWidget(pilot_label)
        pilot_layout.addWidget(self.pilot_input)
        layout.addLayout(pilot_layout)
        
        # Flight Unit
        unit_layout = QHBoxLayout()
        unit_label = QLabel("Flight Unit:")
        unit_label.setFixedWidth(200)
        self.unit_input = QLineEdit()
        self.unit_input.textChanged.connect(self.on_settings_changed)
        unit_layout.addWidget(unit_label)
        unit_layout.addWidget(self.unit_input)
        layout.addLayout(unit_layout)

        # Buffer status
        buffer_layout = QVBoxLayout()
        buffer_layout.setSpacing(12)
        
        buffer_status_layout = QHBoxLayout()
        buffer_status_layout.setSpacing(8)
        buffer_status_label = QLabel("Pre-trigger:")
        buffer_status_label.setFixedWidth(80)
        buffer_status_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.buffer_indicator = QProgressBar()
        self.buffer_indicator.setFixedHeight(20)
        buffer_status_layout.addWidget(buffer_status_label)
        buffer_status_layout.addWidget(self.buffer_indicator)
        buffer_layout.addLayout(buffer_status_layout)
        
        # Recording countdown
        recording_status_layout = QHBoxLayout()
        recording_status_layout.setSpacing(8)
        recording_status_label = QLabel("Recording:")
        recording_status_label.setFixedWidth(80)
        recording_status_label.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.recording_indicator = QProgressBar()
        self.recording_indicator.setFixedHeight(20)
        self.recording_indicator.setValue(0)
        recording_status_layout.addWidget(recording_status_label)
        recording_status_layout.addWidget(self.recording_indicator)
        buffer_layout.addLayout(recording_status_layout)
        
        buffer_layout.addSpacing(4)
        self.status_label = QLabel("Pre-trigger active...")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        buffer_layout.addWidget(self.status_label)
        
        layout.addLayout(buffer_layout)
        
        # Folder buttons
        folder_buttons_layout = QHBoxLayout()
        self.folder_button = QPushButton("Select video folder")
        self.folder_button.clicked.connect(self.select_folder)
        self.folder_button.setFixedHeight(32)
        folder_buttons_layout.addWidget(self.folder_button)
        
        self.open_folder_button = QPushButton("Open video folder")
        self.open_folder_button.clicked.connect(self.open_storage_folder)
        self.open_folder_button.setFixedHeight(32)
        folder_buttons_layout.addWidget(self.open_folder_button)
        layout.addLayout(folder_buttons_layout)
        
        # Folder path - verwijderd
        self.folder_label = QLabel("")
        self.folder_label.hide()  # Verberg de label
        
        # Recent recordings - verwijderd
        self.files_label = QLabel("No recordings found")
        self.files_label.hide()  # Verberg de label
        
        # Bottom buttons layout
        bottom_buttons_layout = QHBoxLayout()
        
        # ProtoDutch button
        proto_button = QPushButton("ProtoDutch")
        proto_button.setFixedHeight(32)
        proto_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(45, 45, 45, 200);
                color: #FFA500;
                border: 1px solid #3d3d3d;
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
                font-family: Bahnschrift;
                font-size: 12pt;
            }
            QPushButton:hover {
                background-color: rgba(60, 60, 60, 200);
                color: #FFD700;
            }
        """)
        proto_button.clicked.connect(lambda: self.open_website("https://www.protodutch.com"))
        bottom_buttons_layout.addWidget(proto_button)

        # Youtube button
        youtube_button = QPushButton("YouTube")
        youtube_button.setFixedHeight(32)
        youtube_button.setStyleSheet("""
            QPushButton {
                background-color: rgba(45, 45, 45, 200);
                color: #FF6666;
                border: 1px solid #3d3d3d;
                padding: 8px;
                border-radius: 4px;
                font-weight: bold;
                font-family: Bahnschrift;
                font-size: 12pt;
            }
            QPushButton:hover {
                background-color: rgba(60, 60, 60, 200);
                color: #FFFFFF;
            }
        """)
        youtube_button.clicked.connect(lambda: self.open_website("https://www.youtube.com/@Dutch-bf109k4"))
        bottom_buttons_layout.addWidget(youtube_button)
        
        layout.addLayout(bottom_buttons_layout)
        
        # Initialize other components
        self.joystick_threads = []
        self.button_monitors = [None, None, None]  # One for each trigger
        self.screen_recorder = None
        self.countdown_timer = QTimer()
        self.countdown_timer.timeout.connect(self.update_countdown)
        self.countdown_seconds = 5
        self.config = configparser.ConfigParser()
        self.normal_color = self.gun_trigger_button.palette().color(QPalette.ColorRole.Button)
        self.active_color = QColor(100, 255, 100)
        
        # Load configuration and start buffer
        self.load_config()
        self.start_buffer()
        self.start_button_monitors()
        
        # Variables for window dragging
        self._drag_pos = None
        layout.mousePressEvent = self._get_drag_start
        layout.mouseMoveEvent = self._get_drag_move

    def _get_drag_start(self, event):
        self._drag_pos = event.pos()
        
    def _get_drag_move(self, event):
        if self._drag_pos is not None:
            self.move(self.pos() + event.pos() - self._drag_pos)

    def load_config(self):
        config_path = os.path.join(os.path.dirname(__file__), 'settings.cfg')
        if os.path.exists(config_path):
            self.config.read(config_path)
        
        if 'Settings' not in self.config:
            self.config['Settings'] = {}
        
        settings = self.config['Settings']
        
        # Load or set default values
        if 'video_path' not in settings:
            settings['video_path'] = str(Path.home() / 'Videos' / 'DCS_GunCam')
            os.makedirs(settings['video_path'], exist_ok=True)
        
        # Disconnect signals temporarily to prevent on_settings_changed from being called
        self.buffer_spinbox.valueChanged.disconnect(self.on_settings_changed)
        self.post_trigger_spinbox.valueChanged.disconnect(self.on_settings_changed)
        self.pilot_input.textChanged.disconnect(self.on_settings_changed)
        self.unit_input.textChanged.disconnect(self.on_settings_changed)
        
        # Load buffer and post-trigger time settings
        if 'buffer_seconds' in settings:
            self.buffer_spinbox.setValue(int(settings['buffer_seconds']))
        else:
            settings['buffer_seconds'] = "10"
            self.buffer_spinbox.setValue(10)
            
        if 'post_trigger_seconds' in settings:
            self.post_trigger_spinbox.setValue(int(settings['post_trigger_seconds']))
        else:
            settings['post_trigger_seconds'] = "10"
            self.post_trigger_spinbox.setValue(10)
        
        # Load pilot name and unit
        if 'pilot_name' in settings:
            self.pilot_input.setText(settings['pilot_name'])
        else:
            settings['pilot_name'] = ""
            self.pilot_input.setText("")
            
        if 'unit_name' in settings:
            self.unit_input.setText(settings['unit_name'])
        else:
            settings['unit_name'] = ""
            self.unit_input.setText("")
            
        # Reconnect signals
        self.buffer_spinbox.valueChanged.connect(self.on_settings_changed)
        self.post_trigger_spinbox.valueChanged.connect(self.on_settings_changed)
        self.pilot_input.textChanged.connect(self.on_settings_changed)
        self.unit_input.textChanged.connect(self.on_settings_changed)
            
        # Load FPS setting
        if 'fps' in settings:
            index = self.fps_combo.findText(settings['fps'])
            if index >= 0:
                self.fps_combo.setCurrentIndex(index)
        else:
            settings['fps'] = self.fps_combo.currentText()
            
        # Load quality setting
        if 'quality' in settings:
            index = self.quality_combo.findText(settings['quality'])
            if index >= 0:
                self.quality_combo.setCurrentIndex(index)
            else:
                self.quality_combo.setCurrentText("Normal (1080p)")
                settings['quality'] = "Normal (1080p)"
        else:
            settings['quality'] = self.quality_combo.currentText()
            self.save_config()  # Save the default quality setting
        
        self.folder_label.setText(settings['video_path'])
        
        # Update trigger button texts with just the button numbers
        for trigger_number in range(1, 4):
            if f'trigger_button_{trigger_number}' in settings:
                self.get_trigger_button(trigger_number).setText(f"Button {settings[f'trigger_button_{trigger_number}']}")
            else:
                self.get_trigger_button(trigger_number).setText("Click to select trigger")
        
        # Update the files list
        self.update_files_list()
        
        # Save the updated settings
        with open(config_path, 'w') as configfile:
            self.config.write(configfile)
        
        # Return the loaded settings for use in screen recorder initialization
        return {
            'video_path': settings['video_path'],
            'buffer_seconds': int(settings['buffer_seconds']),
            'post_trigger_seconds': int(settings['post_trigger_seconds']),
            'quality': settings['quality'],
            'fps': settings['fps'],
            'pilot_name': settings['pilot_name'],
            'unit_name': settings['unit_name']
        }

    def save_config(self):
        settings = self.config['Settings']
        settings['buffer_seconds'] = str(self.buffer_spinbox.value())
        settings['post_trigger_seconds'] = str(self.post_trigger_spinbox.value())
        settings['fps'] = self.fps_combo.currentText()
        settings['quality'] = self.quality_combo.currentText()
        settings['pilot_name'] = self.pilot_input.text()
        settings['unit_name'] = self.unit_input.text()
        
        config_path = os.path.join(os.path.dirname(__file__), 'settings.cfg')
        with open(config_path, 'w') as configfile:
            self.config.write(configfile)

    def select_folder(self):
        settings = self.config['Settings']
        current_path = settings.get('video_path', str(Path.home() / 'Videos' / 'DCS_GunCam'))
        
        # Create a file dialog that shows files in Windows style
        dialog = QFileDialog(self)
        dialog.setWindowTitle("Select folder for video storage")
        dialog.setDirectory(current_path)
        dialog.setFileMode(QFileDialog.FileMode.Directory)
        dialog.setOption(QFileDialog.Option.DontUseNativeDialog)
        dialog.setOption(QFileDialog.Option.ShowDirsOnly, False)
        
        # Set dark title bar for dialog
        dialog.setWindowFlags(dialog.windowFlags() | Qt.WindowType.FramelessWindowHint)
        dialog.setStyleSheet("""
            QDialog, QWidget {
                background-color: #1e1e1e;
                color: white;
            }
            QFileDialog {
                background-color: #1e1e1e;
                color: white;
            }
            QLabel {
                color: white;
            }
            QTreeView, QListView {
                background-color: #1e1e1e;
                color: white;
                border: 1px solid #3d3d3d;
            }
            QTreeView::item:selected, QListView::item:selected {
                background-color: #2d2d2d;
            }
            QTreeView::item:hover, QListView::item:hover {
                background-color: #353535;
            }
            QHeaderView::section {
                background-color: #1e1e1e;
                color: white;
                border: 1px solid #3d3d3d;
            }
            QLineEdit {
                background-color: #2d2d2d;
                color: white;
                border: 1px solid #3d3d3d;
                padding: 2px;
            }
            QPushButton {
                background-color: #2d2d2d;
                color: white;
                border: 1px solid #3d3d3d;
                padding: 5px;
                min-width: 80px;
            }
            QPushButton:hover {
                background-color: #353535;
            }
            QComboBox {
                background-color: #2d2d2d;
                color: white;
                border: 1px solid #3d3d3d;
                padding: 2px;
            }
            QComboBox::drop-down {
                border: none;
                background-color: #2d2d2d;
            }
            QComboBox::down-arrow {
                background-color: #2d2d2d;
                width: 16px;
                height: 16px;
            }
            QScrollBar:vertical {
                background-color: #1e1e1e;
                width: 12px;
                margin: 0px;
            }
            QScrollBar::handle:vertical {
                background-color: #3d3d3d;
                min-height: 20px;
            }
            QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical {
                background: none;
            }
            QScrollBar:horizontal {
                background-color: #1e1e1e;
                height: 12px;
                margin: 0px;
            }
            QScrollBar::handle:horizontal {
                background-color: #3d3d3d;
                min-width: 20px;
            }
            QScrollBar::add-line:horizontal, QScrollBar::sub-line:horizontal {
                background: none;
            }
            QToolButton {
                background-color: #2d2d2d;
                color: white;
                border: 1px solid #3d3d3d;
            }
            QToolButton:hover {
                background-color: #353535;
            }
        """)
        
        if dialog.exec() == QFileDialog.DialogCode.Accepted:
            folder = dialog.selectedFiles()[0]
            try:
                # Create folder if it doesn't exist
                os.makedirs(folder, exist_ok=True)
                
                # Save new folder in config
                settings['video_path'] = folder
                self.folder_label.setText(folder)
                self.save_config()
                
                # Update file list
                self.update_files_list()
                
            except Exception as e:
                QMessageBox.critical(self, "Error", f"Could not create folder: {str(e)}")

    def start_button_monitors(self):
        try:
            settings = self.config['Settings']
            for trigger_number in range(1, 4):
                if f'trigger_button_{trigger_number}' in settings and f'joystick_id_{trigger_number}' in settings:
                    button = int(settings[f'trigger_button_{trigger_number}'])
                    joystick_id = int(settings[f'joystick_id_{trigger_number}'])
                    
                    # Stop any existing monitor
                    if self.button_monitors[trigger_number-1]:
                        self.button_monitors[trigger_number-1].stop()
                        self.button_monitors[trigger_number-1].wait()
                    
                    # Start new monitor
                    self.button_monitors[trigger_number-1] = ButtonMonitorThread(button, joystick_id, self)
                    self.button_monitors[trigger_number-1].button_state_changed.connect(
                        lambda state, tn=trigger_number: self.on_trigger_state_changed(state, tn))
                    self.button_monitors[trigger_number-1].start()
        except Exception as e:
            print(f"Error starting button monitors: {e}")
            QMessageBox.warning(self, "Error", f"Failed to start button monitoring: {str(e)}")

    def update_button_color(self, is_pressed, trigger_number):
        if is_pressed:
            self.get_trigger_button(trigger_number).setStyleSheet("background-color: #64FF64;")  # Licht groen
        else:
            self.get_trigger_button(trigger_number).setStyleSheet("")  # Reset naar standaard kleur
        self.get_trigger_button(trigger_number).update()  # Force visuele update

    def stop_all_threads(self):
        # Stop joystick threads
        for thread in self.joystick_threads:
            thread.stop()
            thread.wait()
        self.joystick_threads.clear()
        
        # Stop button monitor threads
        for monitor in self.button_monitors:
            if monitor:
                monitor.stop()
                monitor.wait()
        self.button_monitors = [None, None, None]

    def get_trigger_button(self, trigger_number):
        if trigger_number == 1:
            return self.gun_trigger_button
        elif trigger_number == 2:
            return self.canon_trigger_button
        else:  # trigger_number == 3
            return self.rockets_trigger_button

    def on_button_pressed(self, button, joystick_name, joystick_id, trigger_number):
        # Update trigger button text immediately
        self.get_trigger_button(trigger_number).setText(f"Setting up: Button {button} on {joystick_name}")
        
        # Wait 2 seconds before setting the trigger
        QTimer.singleShot(2000, lambda: self.finish_button_setup(button, joystick_name, joystick_id, trigger_number))

    def finish_button_setup(self, button, joystick_name, joystick_id, trigger_number):
        settings = self.config['Settings']
        settings[f'trigger_button_{trigger_number}'] = str(button)
        settings[f'joystick_name_{trigger_number}'] = joystick_name
        settings[f'joystick_id_{trigger_number}'] = str(joystick_id)
        self.save_config()
        
        # Update trigger button text with just the button number
        self.get_trigger_button(trigger_number).setText(f"Button {button}")
        self.get_trigger_button(trigger_number).setEnabled(True)
        self.stop_all_threads()
        
        # Start monitoring the new trigger button
        self.start_button_monitors()
        
        # Restart the buffer
        self.start_buffer()

    def on_trigger_state_changed(self, is_pressed, trigger_number):
        """Handle trigger button state changes"""
        self.update_button_color(is_pressed, trigger_number)
        
        if is_pressed:
            # Start or extend recording
            if self.screen_recorder:
                if not self.screen_recorder.triggered:
                    # Start new recording
                    self.countdown_timer.stop()
                    total_recording_time = self.post_trigger_spinbox.value()
                    self.countdown_seconds = total_recording_time
                    self.recording_indicator.setMaximum(total_recording_time)
                    self.recording_indicator.setValue(total_recording_time)
                    self.screen_recorder.start_new_recording()
                    self.status_label.setText(f"Recording started ({self.buffer_spinbox.value()}+{total_recording_time}s total)...")
                else:
                    # Reset countdown timer
                    self.countdown_timer.stop()
                    total_recording_time = self.post_trigger_spinbox.value()
                    self.countdown_seconds = total_recording_time
                    self.recording_indicator.setMaximum(total_recording_time)
                    self.recording_indicator.setValue(total_recording_time)
                    self.screen_recorder.extend_recording()
                    self.status_label.setText(f"Recording extended ({total_recording_time}s from trigger)...")
        else:
            # Start countdown to stop recording
            if self.screen_recorder and self.screen_recorder.triggered:
                self.countdown_timer.start(1000)  # Update every second
                self.status_label.setText(f"Recording stops in {self.countdown_seconds} seconds...")

    def update_countdown(self):
        """Update the countdown timer and stop recording when it reaches zero"""
        if not self.screen_recorder or not self.screen_recorder.triggered:
            self.countdown_timer.stop()
            self.recording_indicator.setValue(0)
            self.status_label.setText("Pre-trigger active...")
            return
            
        self.countdown_seconds -= 1
        self.recording_indicator.setValue(self.countdown_seconds)
        
        if self.countdown_seconds > 0:
            self.status_label.setText(f"Recording stops in {self.countdown_seconds} seconds... ({self.countdown_seconds}s total)")
        else:
            self.countdown_timer.stop()
            self.countdown_seconds = self.buffer_spinbox.value() + self.post_trigger_spinbox.value()
            self.recording_indicator.setValue(0)
            if self.screen_recorder:
                self.screen_recorder.stop()
                self.status_label.setText("Recording stopped, pre-trigger active...")

    def on_recording_started(self):
        print("Recording started...")
        total_recording_time = self.buffer_spinbox.value() + self.post_trigger_spinbox.value()
        self.status_label.setText(f"Recording active ({total_recording_time}s total)...")
        self.recording_indicator.setValue(total_recording_time)

    def on_recording_stopped(self, filepath):
        print(f"Recording saved: {filepath}")
        self.status_label.setText(f"Recording saved: {os.path.basename(filepath)}")
        self.recording_indicator.setValue(0)
        self.update_files_list()
        
        # Start new buffer
        self.start_buffer()
        
        # Reset countdown with total time
        self.countdown_timer.stop()
        self.countdown_seconds = self.buffer_spinbox.value() + self.post_trigger_spinbox.value()

    def start_listening(self, trigger_number):
        try:
            # Ensure pygame is initialized
            if not pygame.get_init():
                pygame.init()
            if not pygame.joystick.get_init():
                pygame.joystick.init()
            
            # Stop existing threads
            self.stop_all_threads()
            
            joystick_count = pygame.joystick.get_count()
            if joystick_count == 0:
                QMessageBox.warning(self, "Error", "No joysticks found!")
                self.get_trigger_button(trigger_number).setEnabled(True)
                return
            
            # Test each joystick
            print("\nDetected joysticks:")
            for i in range(joystick_count):
                try:
                    joy = pygame.joystick.Joystick(i)
                    joy.init()
                    print(f"Joystick {i}: {joy.get_name()} - {joy.get_numbuttons()} buttons")
                    joy.quit()  # Release for thread usage
                except pygame.error as e:
                    print(f"Error initializing joystick {i}: {e}")
                    continue
            
            self.get_trigger_button(trigger_number).setText("Press a button...")
            self.get_trigger_button(trigger_number).setEnabled(False)
            
            # Start threads for all joysticks
            for i in range(joystick_count):
                thread = JoystickThread(i)
                thread.button_pressed.connect(lambda b, n, id, tn=trigger_number: self.on_button_pressed(b, n, id, tn))
                thread.start()
                self.joystick_threads.append(thread)
        except Exception as e:
            print(f"Error in start_listening: {e}")
            QMessageBox.warning(self, "Error", f"Failed to initialize joysticks: {str(e)}")
            self.get_trigger_button(trigger_number).setEnabled(True)

    def open_storage_folder(self):
        settings = self.config['Settings']
        folder_path = settings.get('video_path', '')
        if os.path.exists(folder_path):
            # Open de map in de standaard bestandsverkenner
            if os.name == 'nt':  # Windows
                os.startfile(folder_path)
            else:  # Linux/Mac
                import subprocess
                subprocess.Popen(['xdg-open', folder_path])
        else:
            QMessageBox.warning(self, "Fout", f"Map bestaat niet: {folder_path}")

    def closeEvent(self, event):
        """Stop de background timer bij het sluiten van de applicatie"""
        print("Closing application...")
        self.background_timer.stop()
        self.save_config()
        self.stop_all_threads()
        if hasattr(self, 'screen_recorder'):
            self.screen_recorder.stop()
        pygame.quit()
        event.accept()

    def update_files_list(self):
        settings = self.config['Settings']
        folder_path = settings.get('video_path', '')
        if os.path.exists(folder_path):
            # Find all mp4 files recursively (including subfolders)
            files_text = "Recent recordings:\n"
            found_files = []
            
            for root, dirs, files in os.walk(folder_path):
                for f in files:
                    if f.endswith('.mp4'):
                        full_path = os.path.join(root, f)
                        rel_path = os.path.relpath(full_path, folder_path)
                        mod_time = datetime.fromtimestamp(os.path.getmtime(full_path))
                        size_mb = os.path.getsize(full_path) / (1024 * 1024)
                        found_files.append((full_path, rel_path, mod_time, size_mb))
            
            # Sort by date (newest first) and show last 5
            found_files.sort(key=lambda x: x[2], reverse=True)
            if found_files:
                for _, rel_path, mod_time, size_mb in found_files[:5]:
                    files_text += f"{rel_path}\n"
                    files_text += f"  {mod_time.strftime('%H:%M')} ({size_mb:.1f} MB)\n"
            else:
                files_text = "No recordings found"
            
            self.files_label.setText(files_text)
        else:
            self.files_label.setText("Folder does not exist")

    def start_buffer(self):
        """Start the pre-trigger recording"""
        if not self.screen_recorder or not self.screen_recorder.recording:
            # Get settings from config
            settings = self.config['Settings']
            
            # Create new recorder with current settings
            self.screen_recorder = ScreenRecorder(
                settings['video_path'],
                buffer_seconds=int(settings['buffer_seconds']),
                post_trigger_seconds=int(settings['post_trigger_seconds']),
                quality=settings['quality'],
                fps=settings['fps'],
                pilot_name=settings['pilot_name'],
                unit_name=settings['unit_name']
            )
            
            # Connect signals
            self.screen_recorder.recording_started.connect(self.on_recording_started)
            self.screen_recorder.recording_stopped.connect(self.on_recording_stopped)
            self.screen_recorder.window_changed.connect(self.on_window_changed)
            self.screen_recorder.buffer_status_changed.connect(self.update_buffer_indicator)
            
            # Start the recorder
            self.screen_recorder.start()
            self.status_label.setText("Pre-trigger active...")

    def on_window_changed(self):
        """Handler for window change"""
        if not self.screen_recorder or not self.screen_recorder.triggered:
            self.status_label.setText("Window changed, rebuilding pre-trigger...")
            self.buffer_indicator.setValue(0)  # Reset buffer indicator
            
            # Reset de buffer status na een korte vertraging
            def update_status():
                if self.screen_recorder and not self.screen_recorder.triggered:
                    self.status_label.setText("Pre-trigger active...")
            
            QTimer.singleShot(3000, update_status)  # Verhoogd van 2000 naar 3000ms

    def update_buffer_indicator(self, percentage):
        """Update the buffer indicator with percentage and color"""
        # Ensure percentage is between 0 and 100
        percentage = max(0, min(100, percentage))
        self.buffer_indicator.setValue(int(percentage))
        
        # Calculate color based on percentage (red -> yellow -> green)
        if percentage < 50:
            # Red to yellow (0-50%)
            r = 255
            g = int((percentage / 50) * 255)  # Linear interpolation from 0 to 255
            b = 0
        else:
            # Yellow to green (50-100%)
            r = int(255 - ((percentage - 50) / 50) * 255)  # Linear interpolation from 255 to 0
            g = 255  # Keep green at maximum
            b = 0
            
        # Convert to hex color code
        color = f"#{r:02x}{g:02x}{b:02x}"
            
        self.buffer_indicator.setStyleSheet(f"""
            QProgressBar {{
                border: 1px solid #3d3d3d;
                border-radius: 2px;
                text-align: center;
                background-color: rgba(30, 30, 30, 150);
                min-height: 20px;
                max-height: 20px;
            }}
            QProgressBar::chunk {{
                background-color: {color};
            }}
        """)

    def on_settings_changed(self):
        """Handler for when settings are changed"""
        try:
            # Save new values in config
            settings = self.config['Settings']
            settings['buffer_seconds'] = str(self.buffer_spinbox.value())
            settings['post_trigger_seconds'] = str(self.post_trigger_spinbox.value())
            settings['fps'] = self.fps_combo.currentText()
            settings['quality'] = self.quality_combo.currentText()
            
            # Only update pilot name and unit name if they are not empty
            pilot_name = self.pilot_input.text()
            if pilot_name:
                settings['pilot_name'] = pilot_name
                
            unit_name = self.unit_input.text()
            if unit_name:
                settings['unit_name'] = unit_name
            
            # Save to config file immediately
            config_path = os.path.join(os.path.dirname(__file__), 'settings.cfg')
            with open(config_path, 'w') as configfile:
                self.config.write(configfile)
            
            print(f"Settings changed:")
            print(f"- Pre-trigger duration: {self.buffer_spinbox.value()} seconds")
            print(f"- Post-trigger duration: {self.post_trigger_spinbox.value()} seconds")
            print(f"- Recording quality: {self.quality_combo.currentText()}")
            print(f"- FPS: {self.fps_combo.currentText()}")
            print(f"- Pilot Name: {pilot_name}")
            print(f"- Flight Unit: {unit_name}")
            
            # Update recorder settings if it exists
            if self.screen_recorder:
                # Store triggered state
                old_triggered = self.screen_recorder.triggered
                
                # Update settings safely
                self.screen_recorder.update_settings(
                    self.buffer_spinbox.value(),
                    self.post_trigger_spinbox.value(),
                    self.fps_combo.currentText(),
                    self.pilot_input.text(),
                    self.unit_input.text()
                )
                
                # Restore triggered state if needed
                if old_triggered:
                    self.screen_recorder.triggered = True
                
                self.status_label.setText("Settings updated, pre-trigger active...")
                
        except Exception as e:
            print(f"Error updating settings: {str(e)}")
            self.status_label.setText("Error updating settings")

    def open_website(self, url):
        """Open een website in de standaard browser"""
        import webbrowser
        webbrowser.open(url)

    def rotate_background(self):
        """Wissel naar de volgende achtergrondafbeelding"""
        self.current_background = (self.current_background % 4) + 1  # Aangepast van 3 naar 4
        self.load_current_background()
        
    def load_current_background(self):
        """Laad de huidige achtergrondafbeelding"""
        try:
            bg_path = os.path.join(os.path.dirname(__file__), f"Images/guncam_bg_source_{self.current_background}.jpg")
            if os.path.exists(bg_path):
                # Laad de originele afbeelding
                background = QPixmap(bg_path)
                
                # Bereken de juiste schaling om de hele window te vullen
                window_ratio = 900 / 700  # window breedte / hoogte
                image_ratio = background.width() / background.height()
                
                if image_ratio > window_ratio:
                    # Afbeelding is relatief breder dan window, schaal op hoogte
                    scaled_height = 700
                    scaled_width = int(700 * image_ratio)
                else:
                    # Afbeelding is relatief hoger dan window, schaal op breedte
                    scaled_width = 900
                    scaled_height = int(900 / image_ratio)
                
                # Schaal de afbeelding
                scaled_bg = background.scaled(scaled_width, scaled_height, 
                                           Qt.AspectRatioMode.KeepAspectRatio,
                                           Qt.TransformationMode.SmoothTransformation)
                
                # Bereken het uitsnede gebied om te centreren
                x = max(0, (scaled_width - 900) // 2)
                y = max(0, (scaled_height - 700) // 2)
                
                # Knip de afbeelding bij naar window formaat
                cropped_bg = scaled_bg.copy(x, y, 900, 700)
                
                # Stel de uitgesneden en geschaalde afbeelding in
                self.background_label.setPixmap(cropped_bg)
            else:
                print(f"Warning: Background image not found: {bg_path}")
        except Exception as e:
            print(f"Error loading background: {str(e)}")

def main():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())

if __name__ == "__main__":
    main() 