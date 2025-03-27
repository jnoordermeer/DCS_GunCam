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

    def on_trigger_state_changed(self, is_pressed, trigger_number):
        """
        Toggle de opname op basis van de buttontransitie.
        We reageren alleen op het moment dat de button ingedrukt wordt (transition van off naar on).
        Als er al wordt opgenomen, stoppen we de opname wanneer de button losgelaten wordt.
        """
        # Print de status voor debug
        print(f"Trigger {trigger_number} state changed: {is_pressed}")
        
        if is_pressed:
            # Button gaat van uit naar aan: start opname als die nog niet bezig is.
            if self.screen_recorder and not self.screen_recorder.triggered:
                self.screen_recorder.start_new_recording()
                self.status_label.setText("Recording started...")
            else:
                # Als er al wordt opgenomen, kun je er ook voor kiezen om de opname te verlengen of niets te doen.
                self.status_label.setText("Recording already active, ignoring press.")
        else:
            # Button gaat van aan naar uit: stop de opname als die bezig is.
            if self.screen_recorder and self.screen_recorder.triggered:
                self.screen_recorder.stop()
                self.status_label.setText("Recording stopped, pre-trigger active...")
        
        # Update de knop kleur op basis van de nieuwe status
        self.update_button_color(is_pressed, trigger_number)
        
        # Als we een countdown timer hebben, update deze
        if hasattr(self, 'countdown_timer'):
            if is_pressed and not self.screen_recorder.triggered:
                self.countdown_timer.start(1000)  # Start timer als we beginnen met opnemen
            elif not is_pressed and self.screen_recorder.triggered:
                self.countdown_timer.stop()  # Stop timer als we stoppen met opnemen

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