#!/usr/bin/env python3
"""
Wave2Joy - Stochastic & Constant Haptic Vibration Controller
===========================================================
A sophisticated vibration pattern generator for game controllers with
extensive GUI customization options and distinct operating modes.

Requirements:
    pip install pygame

Usage:
    python wave2joy.py
"""

import pygame
import sys
import time
import threading
import math
import random
import json
from collections import deque
from typing import Tuple, Optional, Dict

# ============================================================================
# GLOBAL CONSTANTS
# ============================================================================

UPDATE_INTERVAL_MS = 10
STARTUP_RAMP_MS = 40
FADEOUT_MS = 500
CROSSFADE_MS = 100
MAX_INTENSITY = 255
STOCHASTIC_START_INTENSITY_MULTIPLIER = 0.30

# Constants for the new pulse modes
CONSTANT_PULSE_BUZZ_MS = 200
CONSTANT_PULSE_GAP_MS = 100

# GUI Constants
WINDOW_WIDTH = 1400
WINDOW_HEIGHT = 950
BG_COLOR = (20, 20, 30)
PANEL_COLOR = (30, 30, 45)
ACCENT_COLOR = (80, 120, 200)
TEXT_COLOR = (220, 220, 230)
BUTTON_COLOR = (50, 80, 140)
BUTTON_HOVER = (70, 100, 160)
SLIDER_COLOR = (60, 60, 80)
ACTIVE_COLOR = (100, 200, 100)
WARNING_COLOR = (200, 100, 100)
INPUT_BOX_COLOR = (40, 40, 60)

# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp value between min and max."""
    return max(min_val, min(max_val, value))

def ease_in_quad(t: float) -> float:
    """Quadratic ease-in curve (t*t) for a smoother ramp."""
    return t * t

# ============================================================================
# GUI COMPONENTS
# ============================================================================

class Button:
    """Simple button widget."""
    def __init__(self, x, y, width, height, text, callback=None):
        self.rect = pygame.Rect(x, y, width, height)
        self.text = text
        self.callback = callback
        self.hovered = False
        self.enabled = True
        
    def draw(self, screen, font):
        color = BUTTON_HOVER if self.hovered and self.enabled else BUTTON_COLOR
        if not self.enabled:
            color = (40, 40, 50)
        pygame.draw.rect(screen, color, self.rect, border_radius=5)
        pygame.draw.rect(screen, ACCENT_COLOR, self.rect, 2, border_radius=5)
        
        text_surf = font.render(self.text, True, TEXT_COLOR if self.enabled else (100, 100, 110))
        text_rect = text_surf.get_rect(center=self.rect.center)
        screen.blit(text_surf, text_rect)
        
    def handle_event(self, event):
        if not self.enabled:
            return False
        
        if event.type == pygame.MOUSEMOTION:
            self.hovered = self.rect.collidepoint(event.pos)
        elif event.type == pygame.MOUSEBUTTONDOWN:
            if self.rect.collidepoint(event.pos):
                if self.callback:
                    self.callback()
                return True
        return False

class Slider:
    """Slider widget for numeric input."""
    def __init__(self, x, y, width, label, min_val, max_val, default_val, step=1):
        self.rect = pygame.Rect(x, y, width, 20)
        self.label = label
        self.min_val = min_val
        self.max_val = max_val
        self.value = default_val
        self.step = step
        self.dragging = False
        self.label_rect = None # For tooltip hit detection
        
    def draw(self, screen, font_small):
        # Label
        if isinstance(self.step, float):
            display_value = f"{self.value:.2f}"
        else:
            display_value = f"{int(self.value)}"
        
        label_text = f"{self.label}: {display_value}"
        label_surf = font_small.render(label_text, True, TEXT_COLOR)
        
        self.label_rect = label_surf.get_rect(topleft=(self.rect.x, self.rect.y - 20))
        screen.blit(label_surf, self.label_rect)
        
        # Track
        pygame.draw.rect(screen, SLIDER_COLOR, self.rect, border_radius=3)
        
        # Fill
        progress = (self.value - self.min_val) / (self.max_val - self.min_val)
        fill_rect = pygame.Rect(self.rect.x, self.rect.y, 
                               int(self.rect.width * progress), self.rect.height)
        pygame.draw.rect(screen, ACCENT_COLOR, fill_rect, border_radius=3)
        
        # Handle
        handle_x = self.rect.x + int(self.rect.width * progress)
        pygame.draw.circle(screen, TEXT_COLOR, (handle_x, self.rect.centery), 8)
        
    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            clickable_area = pygame.Rect(self.rect.x, self.rect.y - 10, self.rect.width, self.rect.height + 20)
            if clickable_area.collidepoint(event.pos):
                self.dragging = True
                progress = clamp((event.pos[0] - self.rect.x) / self.rect.width, 0, 1)
                raw_value = self.min_val + progress * (self.max_val - self.min_val)
                self.value = round(raw_value / self.step) * self.step
                return True
        elif event.type == pygame.MOUSEBUTTONUP:
            self.dragging = False
        elif event.type == pygame.MOUSEMOTION and self.dragging:
            progress = clamp((event.pos[0] - self.rect.x) / self.rect.width, 0, 1)
            raw_value = self.min_val + progress * (self.max_val - self.min_val)
            self.value = round(raw_value / self.step) * self.step
            return True
        return False

class Dropdown:
    """Dropdown menu widget."""
    def __init__(self, x, y, width, label, options, default_index=0):
        self.rect = pygame.Rect(x, y, width, 30)
        self.label = label
        self.options = options
        self.selected_index = default_index
        self.expanded = False
        self.label_rect = None # For tooltip hit detection
        
    def draw(self, screen, font_small):
        # Label
        label_surf = font_small.render(self.label, True, TEXT_COLOR)
        self.label_rect = label_surf.get_rect(topleft=(self.rect.x, self.rect.y - 20))
        screen.blit(label_surf, self.label_rect)
        
        # Main box
        pygame.draw.rect(screen, PANEL_COLOR, self.rect, border_radius=3)
        pygame.draw.rect(screen, ACCENT_COLOR, self.rect, 2, border_radius=3)
        
        # Selected text
        text_surf = font_small.render(self.options[self.selected_index], True, TEXT_COLOR)
        text_rect = text_surf.get_rect(centery=self.rect.centery)
        text_rect.x = self.rect.x + 10
        screen.blit(text_surf, text_rect)
        
        # Arrow
        arrow = "▼" if not self.expanded else "▲"
        arrow_surf = font_small.render(arrow, True, TEXT_COLOR)
        arrow_rect = arrow_surf.get_rect(centery=self.rect.centery)
        arrow_rect.right = self.rect.right - 10
        screen.blit(arrow_surf, arrow_rect)
        
        # Dropdown list
        if self.expanded:
            for i, option in enumerate(self.options):
                option_rect = pygame.Rect(self.rect.x, self.rect.y + 35 + i * 30, 
                                         self.rect.width, 30)
                color = BUTTON_HOVER if i == self.selected_index else PANEL_COLOR
                pygame.draw.rect(screen, color, option_rect, border_radius=3)
                pygame.draw.rect(screen, ACCENT_COLOR, option_rect, 1, border_radius=3)
                
                opt_surf = font_small.render(option, True, TEXT_COLOR)
                opt_rect = opt_surf.get_rect(centery=option_rect.centery)
                opt_rect.x = option_rect.x + 10
                screen.blit(opt_surf, opt_rect)
    
    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            if self.rect.collidepoint(event.pos):
                self.expanded = not self.expanded
                return True
            elif self.expanded:
                for i in range(len(self.options)):
                    option_rect = pygame.Rect(self.rect.x, self.rect.y + 35 + i * 30, 
                                            self.rect.width, 30)
                    if option_rect.collidepoint(event.pos):
                        self.selected_index = i
                        self.expanded = False
                        return True
                self.expanded = False
        return False
    
    def get_selected(self):
        return self.options[self.selected_index]

class TextInputBox:
    """A simple text input box widget."""
    def __init__(self, x, y, width, height, font):
        self.rect = pygame.Rect(x, y, width, height)
        self.font = font
        self.text = ""
        self.active = False
        self.cursor_visible = True
        self.cursor_timer = 0

    def handle_event(self, event):
        if event.type == pygame.MOUSEBUTTONDOWN:
            self.active = self.rect.collidepoint(event.pos)
        if event.type == pygame.KEYDOWN and self.active:
            if event.key == pygame.K_BACKSPACE:
                self.text = self.text[:-1]
            elif event.key == pygame.K_RETURN:
                # Can be used to trigger save, but we'll use a button for clarity
                pass
            else:
                self.text += event.unicode
            return True
        return False

    def draw(self, screen):
        # Box
        color = ACCENT_COLOR if self.active else SLIDER_COLOR
        pygame.draw.rect(screen, INPUT_BOX_COLOR, self.rect, border_radius=3)
        pygame.draw.rect(screen, color, self.rect, 2, border_radius=3)
        
        # Text
        text_surf = self.font.render(self.text, True, TEXT_COLOR)
        screen.blit(text_surf, (self.rect.x + 8, self.rect.y + (self.rect.height - text_surf.get_height()) // 2))

        # Blinking Cursor
        if self.active:
            self.cursor_timer += 1
            if self.cursor_timer > 30: # Blink speed
                self.cursor_visible = not self.cursor_visible
                self.cursor_timer = 0
            if self.cursor_visible:
                cursor_x = self.rect.x + 8 + text_surf.get_width()
                cursor_y = self.rect.y + 8
                pygame.draw.line(screen, TEXT_COLOR, (cursor_x, cursor_y), (cursor_x, self.rect.bottom - 8), 2)

# ============================================================================
# PATTERN GENERATOR CLASS
# ============================================================================

class HapticPatternGenerator:
    """Generates stochastic and preset vibration patterns."""
    
    def __init__(self, config: Dict):
        self.config = config
        self.start_time = None
        self.current_time = 0.0
        
        # Stochastic state
        self.left_intensity = 0.0
        self.right_intensity = 0.0
        self.active_motor = None
        self.motor_switch_time = 0.0
        self.current_phase = 'gap'
        self.phase_start_time = 0.0
        self.phase_duration = 0.0
        self.next_motor = 'left'
        self.motor_history = deque(maxlen=5)
        self.left_consecutive = 0
        self.right_consecutive = 0
        self.resonance_mode = None
        self.resonance_start_time = 0.0
        self.resonance_duration = 0.0
        self.last_resonance_check = 0.0
        
        # State for constant pulse modes
        self.pulse_time = 0.0
        
        # State for Cycle mode
        self.cycle_phase_index = 0
        self.last_pulse_cycle_index = -1
        
        # State for Breathing Pulse mode
        self.breathing_time = 0.0
        self.breathing_phase = 'buzz' # 'buzz' or 'gap'
        self.breathing_phase_end_time = 0.0
        
    def start(self):
        """Start the pattern generator."""
        self.start_time = time.time()
        self.current_time = 0.0
        self.pulse_time = 0.0
        self.cycle_phase_index = 0
        self.last_pulse_cycle_index = -1
        self.breathing_time = 0.0
        self.breathing_phase = 'buzz'
        self.breathing_phase_end_time = 0.0
        
    def get_global_multiplier(self) -> float:
        """Calculate global intensity multiplier for STOCHASTIC mode."""
        if self.config['peak_time'] <= 0:
            progress = 1.0
        elif self.current_time >= self.config['peak_time']:
            progress = 1.0
        else:
            progress = self.current_time / self.config['peak_time']
        
        eased_progress = ease_in_quad(progress)
        
        base_mult = STOCHASTIC_START_INTENSITY_MULTIPLIER + (1.0 - STOCHASTIC_START_INTENSITY_MULTIPLIER) * eased_progress
        
        breathing = 1.0 + self.config['breathing_amount'] * math.sin(
            2 * math.pi * self.current_time / self.config['breathing_period']
        )
        
        return base_mult * breathing
    
    def select_next_motor(self) -> str:
        """Select next motor with probabilistic alternation."""
        left_count = self.motor_history.count('left')
        right_count = self.motor_history.count('right')
        
        if self.left_consecutive >= 2: return 'right'
        elif self.right_consecutive >= 2: return 'left'
        
        alternation_bias = self.config['alternation_bias']
        
        if left_count > right_count:
            return 'right' if random.random() < alternation_bias else 'left'
        elif right_count > left_count:
            return 'left' if random.random() < alternation_bias else 'right'
        else:
            return random.choice(['left', 'right'])
    
    def generate_buzz_duration(self) -> float:
        """Generate random buzz duration."""
        min_buzz = self.config['buzz_min'] / 1000.0
        max_buzz = self.config['buzz_max'] / 1000.0
        return random.uniform(min_buzz, max_buzz)
    
    def generate_gap_duration(self) -> float:
        """Generate random gap with bias toward shorter gaps."""
        max_gap_s = self.config['max_gap'] / 1000.0
        min_gap_s = self.config['gap_min'] / 1000.0
        
        t = random.betavariate(2, 3)
        gap = min_gap_s + t * (max_gap_s - min_gap_s)
        return gap
    
    def get_base_intensity(self) -> float:
        """Get base intensity by picking a random value between weak and strong."""
        weak = min(self.config['weak'], self.config['strong'])
        strong = max(self.config['weak'], self.config['strong'])
        base = random.uniform(weak, strong)
        return clamp(base, 0, MAX_INTENSITY)
    
    def check_resonance_trigger(self):
        """Check for resonance mode triggers."""
        if self.resonance_mode is not None or not self.config['resonance_enabled']:
            return
        
        check_interval = self.config['resonance_check_interval']
        if self.current_time - self.last_resonance_check >= check_interval:
            self.last_resonance_check = self.current_time
            
            if random.random() < self.config['resonance_probability']:
                modes = ['mirrored', 'anti_phase', 'offset']
                self.resonance_mode = random.choice(modes)
                self.resonance_start_time = self.current_time
                self.resonance_duration = random.uniform(
                    self.config['resonance_duration_min'],
                    self.config['resonance_duration_max']
                )
    
    def update_stochastic(self, dt: float) -> Tuple[float, float]:
        """Update stochastic pattern. This is the complex, unpredictable mode."""
        self.current_time += dt
        self.check_resonance_trigger()
        
        if self.resonance_mode is not None:
            elapsed = self.current_time - self.resonance_start_time
            if elapsed >= self.resonance_duration:
                self.resonance_mode = None
            else:
                return self.update_resonance_mode(elapsed)
        
        phase_elapsed = self.current_time - self.phase_start_time
        if phase_elapsed >= self.phase_duration:
            if self.current_phase == 'gap':
                self.current_phase = 'buzz'
                self.phase_duration = self.generate_buzz_duration()
                self.next_motor = self.select_next_motor()
                self.motor_history.append(self.next_motor)
                if self.next_motor == 'left':
                    self.left_consecutive += 1
                    self.right_consecutive = 0
                else:
                    self.right_consecutive += 1
                    self.left_consecutive = 0
                self.motor_switch_time = self.current_time
            else:
                self.current_phase = 'gap'
                self.phase_duration = self.generate_gap_duration()
            self.phase_start_time = self.current_time
        
        global_mult = self.get_global_multiplier()
        if self.current_phase == 'buzz':
            base_intensity = self.get_base_intensity()
            target_intensity = base_intensity * global_mult
            
            switch_elapsed = self.current_time - self.motor_switch_time
            if switch_elapsed < (CROSSFADE_MS / 1000.0):
                target_intensity *= (switch_elapsed / (CROSSFADE_MS / 1000.0))
            
            if self.current_time < (STARTUP_RAMP_MS / 1000.0):
                target_intensity *= (self.current_time / (STARTUP_RAMP_MS / 1000.0))
            
            if self.next_motor == 'left':
                left = target_intensity
                right = 0.0
                if (self.config['trigger_enabled'] and target_intensity > self.config['strong'] and 
                    phase_elapsed > self.config['trigger_delay']):
                    right = self.config['weak'] * self.config['trigger_intensity'] * global_mult
            else:
                right = target_intensity
                left = 0.0
                if (self.config['trigger_enabled'] and target_intensity > self.config['strong'] and 
                    phase_elapsed > self.config['trigger_delay']):
                    left = self.config['weak'] * self.config['trigger_intensity'] * global_mult
        else:
            left, right = 0.0, 0.0
        
        return clamp(left, 0, MAX_INTENSITY), clamp(right, 0, MAX_INTENSITY)
    
    def update_resonance_mode(self, elapsed: float) -> Tuple[float, float]:
        """Update resonance mode patterns."""
        global_mult = self.get_global_multiplier()
        base = self.config['weak'] * global_mult * self.config['resonance_intensity']
        freq = self.config['resonance_frequency']
        phase = 2 * math.pi * freq * elapsed
        
        if self.resonance_mode == 'mirrored':
            intensity = base * (0.5 + 0.5 * math.sin(phase))
            return intensity, intensity
        elif self.resonance_mode == 'anti_phase':
            left = base * (0.5 + 0.5 * math.sin(phase))
            right = base * (0.5 + 0.5 * math.sin(phase + math.pi))
            return left, right
        elif self.resonance_mode == 'offset':
            left = base * (0.5 + 0.5 * math.sin(phase))
            right = base * (0.5 + 0.5 * math.sin(phase + math.pi / 2))
            return left, right
        return 0.0, 0.0
    
    def update_constant_pulse(self, dt: float, mode: str) -> Tuple[float, float]:
        """Update constant pulse patterns. No ramping, no randomness."""
        self.pulse_time += dt * 1000 # work in milliseconds
        
        total_pulse_duration = CONSTANT_PULSE_BUZZ_MS + CONSTANT_PULSE_GAP_MS
        phase_time = self.pulse_time % total_pulse_duration
        
        left, right = 0.0, 0.0
        
        if phase_time < CONSTANT_PULSE_BUZZ_MS:
            # In the BUZZ part of the pulse
            intensity = 0.0
            if mode == 'constant_weak':
                intensity = self.config['weak']
            elif mode == 'constant_strong':
                intensity = self.config['strong']
            elif mode == 'constant_max':
                intensity = self.config['max']
            elif mode == 'constant_ac':
                intensity = self.config['max']
            
            if mode == 'constant_ac':
                # Alternate motors on each full pulse cycle
                cycle_index = math.floor(self.pulse_time / total_pulse_duration)
                if cycle_index % 2 == 0:
                    left = intensity
                else:
                    right = intensity
            else:
                left, right = intensity, intensity
        
        return clamp(left, 0, MAX_INTENSITY), clamp(right, 0, MAX_INTENSITY)

    def update_cycle_pulse(self, dt: float) -> Tuple[float, float]:
        """Update the pulse-by-pulse cycle mode."""
        self.pulse_time += dt * 1000  # work in milliseconds

        total_pulse_duration = CONSTANT_PULSE_BUZZ_MS + CONSTANT_PULSE_GAP_MS
        
        # Determine if a new pulse cycle has started
        current_pulse_cycle_index = math.floor(self.pulse_time / total_pulse_duration)
        if current_pulse_cycle_index > self.last_pulse_cycle_index:
            self.cycle_phase_index = (self.cycle_phase_index + 1) % 4
            self.last_pulse_cycle_index = current_pulse_cycle_index

        phase_time = self.pulse_time % total_pulse_duration
        left, right = 0.0, 0.0

        if phase_time < CONSTANT_PULSE_BUZZ_MS:
            # We are in the "buzz" part of the pulse
            current_phase = self.cycle_phase_index
            
            if current_phase == 0:  # Phase 1: Strong, both motors
                intensity = self.config['strong']
                left, right = intensity, intensity
            elif current_phase == 1:  # Phase 2: Max, both motors
                intensity = self.config['max']
                left, right = intensity, intensity
            elif current_phase == 2:  # Phase 3: Max, left motor only
                intensity = self.config['max']
                left, right = intensity, 0.0
            elif current_phase == 3:  # Phase 4: Max, right motor only
                intensity = self.config['max']
                left, right = 0.0, intensity

        return clamp(left, 0, MAX_INTENSITY), clamp(right, 0, MAX_INTENSITY)

    def update_breathing_pulse(self, dt: float) -> Tuple[float, float]:
        """Update the breathing pulse mode with beat frequencies and gaps."""
        self.current_time += dt

        if self.breathing_phase == 'buzz':
            self.breathing_time += dt
            
            # Check if the buzz phase (N cycles) is over
            buzz_duration = self.config['breathing_pulse_cycles'] * self.config['breathing_pulse_period']
            if self.breathing_time >= buzz_duration:
                gap_duration = self.config['breathing_pulse_gap']
                if gap_duration > 0:
                    self.breathing_phase = 'gap'
                    self.breathing_phase_end_time = self.current_time + gap_duration
                    return 0.0, 0.0
                else:
                    # No gap, just loop the breathing time
                    self.breathing_time = 0.0

            # Get parameters from config
            min_val = self.config['breathing_pulse_min_intensity']
            max_val = self.config['max']
            base_period = self.config['breathing_pulse_period']
            sync_period = self.config['breathing_pulse_sync_period']
            
            base_freq = 1.0 / base_period if base_period > 0 else 0
            beat_freq = 1.0 / sync_period if sync_period > 0 else 0
            
            freq_left = base_freq
            freq_right = base_freq + beat_freq
            
            center = (max_val + min_val) / 2.0
            amplitude = (max_val - min_val) / 2.0
            
            phase_left = 2 * math.pi * freq_left * self.breathing_time
            intensity_left = center + amplitude * math.sin(phase_left)
            
            phase_right = 2 * math.pi * freq_right * self.breathing_time
            intensity_right = center + amplitude * math.sin(phase_right)
            
            return clamp(intensity_left, 0, MAX_INTENSITY), clamp(intensity_right, 0, MAX_INTENSITY)

        elif self.breathing_phase == 'gap':
            if self.current_time >= self.breathing_phase_end_time:
                # Gap is over, switch back to buzz
                self.breathing_phase = 'buzz'
                self.breathing_time = 0.0
            return 0.0, 0.0
        
        return 0.0, 0.0

# ============================================================================
# CONTROLLER MANAGER
# ============================================================================

class ControllerManager:
    """Manages controller connection and vibration."""
    
    def __init__(self):
        self.joystick = None
        self.supports_rumble = False
        
    def initialize(self) -> bool:
        """Initialize and detect controller."""
        try:
            pygame.joystick.init()
            joystick_count = pygame.joystick.get_count()
            if joystick_count == 0: return False
            for i in range(joystick_count):
                joy = pygame.joystick.Joystick(i)
                joy.init()
                try:
                    if joy.rumble(0, 0, 0):
                        self.joystick = joy
                        self.supports_rumble = True
                        print(f"[DEBUG] Controller '{joy.get_name()}' supports rumble.")
                        return True
                except pygame.error:
                    pass
            return False
        except pygame.error:
            return False
    
    def set_rumble(self, left: float, right: float):
        """Set rumble intensities."""
        if self.joystick and self.supports_rumble:
            left_norm = clamp(left / 255.0, 0.0, 1.0)
            right_norm = clamp(right / 255.0, 0.0, 1.0)
            try:
                self.joystick.rumble(left_norm, right_norm, 100)
            except pygame.error:
                pass
    
    def stop(self):
        """Stop rumble."""
        if self.joystick and self.supports_rumble:
            try:
                self.joystick.rumble(0, 0, 0)
            except pygame.error:
                pass
    
    def get_name(self) -> str:
        """Get controller name."""
        if self.joystick:
            return self.joystick.get_name()
        return "None"

# ============================================================================
# PRESET MANAGER
# ============================================================================

class PresetManager:
    """Manages default and user-saved configuration presets."""
    
    def __init__(self, filepath="user_presets.json"):
        self.filepath = filepath
        self.default_presets = self._get_default_presets()
        self.custom_presets = self.load_custom_presets()

    def load_custom_presets(self) -> Dict:
        """Loads custom presets from the JSON file."""
        try:
            with open(self.filepath, 'r') as f:
                return json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            return {}

    def save_custom_presets(self):
        """Saves the current custom presets to the JSON file."""
        with open(self.filepath, 'w') as f:
            json.dump(self.custom_presets, f, indent=4)

    def get_all_presets(self) -> Dict:
        """Returns a merged dictionary of default and custom presets."""
        return {**self.default_presets, **self.custom_presets}

    def save_preset(self, name: str, config: Dict):
        """Saves a new custom preset."""
        if name and name not in self.default_presets:
            self.custom_presets[name] = config
            self.save_custom_presets()

    def delete_preset(self, name: str):
        """Deletes a custom preset."""
        if name in self.custom_presets:
            del self.custom_presets[name]
            self.save_custom_presets()
    
    def is_custom_preset(self, name: str) -> bool:
        """Checks if a preset is a custom one."""
        return name in self.custom_presets

    @staticmethod
    def get_default_config():
        """Get default configuration."""
        return {
            'session_length': 60, 'peak_time': 60, 'weak': 60, 'strong': 160, 'max': 255,
            'buzz_min': 100, 'buzz_max': 2000, 'gap_min': 100, 'max_gap': 270,
            'variance': 0.125, 'alternation_bias': 0.7, 'breathing_amount': 0.1, 'breathing_period': 15.0,
            'trigger_enabled': True, 'trigger_delay': 0.5, 'trigger_intensity': 0.5,
            'resonance_enabled': True, 'resonance_probability': 0.1, 'resonance_check_interval': 5.0,
            'resonance_duration_min': 2.0, 'resonance_duration_max': 5.0, 'resonance_frequency': 2.0,
            'resonance_intensity': 1.0, 'mode': 'stochastic',
            'breathing_pulse_period': 8.0, 'breathing_pulse_sync_period': 30.0,
            'breathing_pulse_min_intensity': 80, 'breathing_pulse_cycles': 1, 'breathing_pulse_gap': 0.0,
        }
    
    @staticmethod
    def _get_default_presets():
        """Get preset configurations."""
        return {
            'Gentle Massage': {'session_length': 300, 'peak_time': 300, 'weak': 40, 'strong': 100, 'buzz_min': 200, 'buzz_max': 1000, 'gap_min': 200, 'max_gap': 1500, 'variance': 0.1, 'breathing_amount': 0.15, 'resonance_probability': 0.05},
            'Standard Session': {'session_length': 1620, 'peak_time': 1620, 'weak': 60, 'strong': 160, 'buzz_min': 100, 'buzz_max': 2000, 'max_gap': 1800, 'variance': 0.125},
            'Intense Workout': {'session_length': 900, 'peak_time': 600, 'weak': 100, 'strong': 200, 'max': 255, 'buzz_min': 150, 'buzz_max': 2500, 'gap_min': 50, 'max_gap': 1000, 'variance': 0.15, 'alternation_bias': 0.8, 'resonance_probability': 0.15},
            'Quick Test': {'session_length': 60, 'peak_time': 30, 'weak': 80, 'strong': 160, 'buzz_min': 200, 'buzz_max': 800, 'max_gap': 500},
            'Rhythmic Flow': {'session_length': 600, 'peak_time': 600, 'weak': 70, 'strong': 150, 'buzz_min': 300, 'buzz_max': 1200, 'max_gap': 1000, 'variance': 0.08, 'breathing_amount': 0.2, 'breathing_period': 10.0, 'resonance_enabled': True, 'resonance_probability': 0.2, 'resonance_duration_min': 3.0, 'resonance_duration_max': 7.0},
            'Cycle': {'session_length': 3600, 'peak_time': 1620, 'weak': 60, 'strong': 160, 'max': 255, 'buzz_min': 100, 'buzz_max': 2000, 'max_gap': 1800, 'variance': 0.125},
            'Breathing Pulse': {'session_length': 3600, 'strong': 150, 'max': 220, 'breathing_pulse_period': 10.0, 
                                'breathing_pulse_sync_period': 45.0, 'breathing_pulse_min_intensity': 150, 
                                'breathing_pulse_cycles': 2, 'breathing_pulse_gap': 1.5},
        }

# ============================================================================
# MAIN GUI APPLICATION
# ============================================================================

class Wave2JoyGUI:
    """Main GUI application."""
    
    def __init__(self):
        pygame.init()
        self.screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
        pygame.display.set_caption("Wave2Joy - Haptic Controller")
        self.clock = pygame.time.Clock()
        
        # Fonts
        self.font_large = pygame.font.Font(None, 36)
        self.font_medium = pygame.font.Font(None, 24)
        self.font_small = pygame.font.Font(None, 18)
        
        self.preset_manager = PresetManager()
        
        # State
        self.running = True
        self.session_active = False
        self.session_thread = None
        self.session_completed_flag = False
        self.config = self.preset_manager.get_default_config()
        
        # Controller
        self.controller = ControllerManager()
        self.controller_connected = self.controller.initialize()
        
        self.session_start_time = 0
        self.current_left = 0.0
        self.current_right = 0.0
        
        # Tooltip state and content
        self.active_tooltip_text = None
        self.tooltips = {
            'preset': "Load pre-configured settings for different experiences.",
            'mode': "Choose the core behavior of the vibration pattern.\n'stochastic' is random, others are predictable.",
            'session_length': "The total duration of the vibration session in seconds.",
            'peak_time': "Time it takes for stochastic intensity to ramp up\nfrom 30% to its maximum. (Stochastic mode only)",
            'weak': "The lower boundary for random intensity vibrations.",
            'strong': "The upper boundary for random intensity vibrations.",
            'max': "The intensity used for 'Constant Max' and 'AC' modes.\nAlso the high point for Breathing Pulse mode.",
            'buzz_min': "The shortest possible duration for a single vibration.",
            'buzz_max': "The longest possible duration for a single vibration.",
            'gap_min': "The shortest possible pause between vibrations.",
            'max_gap': "The longest possible pause between vibrations.",
            'alternation_bias': "How strongly the pattern tries to switch between left/right motors.\nHigher values mean more switching.",
            'variance': "Legacy setting, has minimal effect in the current version.",
            'breathing_amount': "The strength of the slow, wave-like intensity pulse.\nSet to 0 to disable. (Stochastic mode only)",
            'breathing_period': "How long one full 'breath' (wave) takes in seconds. (Stochastic mode only)",
            'trigger_delay': "How long a strong buzz must last before the other motor gives a small kick.",
            'trigger_intensity': "How strong the small kick from the other motor is.",
            'resonance_probability': "The chance that a synchronized, rhythmic pattern will occur.",
            'resonance_frequency': "How fast the synchronized resonance pattern pulses.",
            'resonance_intensity': "An intensity multiplier for the resonance effect.",
            'resonance_duration_min': "The minimum time a resonance effect can last.",
            'resonance_duration_max': "The maximum time a resonance effect can last.",
            'breathing_pulse_period': "Controls the main speed of the breathing pulse.\nLower values mean faster breathing. (Breathing Pulse mode only)",
            'breathing_pulse_sync_period': "How often the left and right motors will harmonize together.\nHigher values mean they sync up less often. (Breathing Pulse mode only)",
            'breathing_pulse_min_intensity': "The lowest intensity point for the breathing wave. (Breathing Pulse mode only)",
            'breathing_pulse_cycles': "How many breathing cycles to perform before a gap.",
            'breathing_pulse_gap': "The duration of the silent gap between cycles in seconds. Set to 0 for no gap.",
        }
        
        # UI Elements
        self.sections = []
        self.sliders = {}
        self.create_ui()
        
    def create_ui(self):
        """Create all UI elements using a dynamic layout system."""
        all_presets = self.preset_manager.get_all_presets()
        preset_names = ['Custom'] + list(all_presets.keys())
        self.preset_dropdown = Dropdown(20, 80, 250, "Preset:", preset_names, 0)
        
        modes = ['stochastic', 'breathing_pulse', 'constant_weak', 'constant_strong', 'constant_max', 'constant_ac', 'cycle']
        default_mode_index = modes.index('breathing_pulse') if 'breathing_pulse' in modes else 0
        self.mode_dropdown = Dropdown(290, 80, 200, "Mode:", modes, default_mode_index)
        
        # UI for saving/deleting presets
        preset_name_label = self.font_small.render("Preset Name:", True, TEXT_COLOR)
        self.screen.blit(preset_name_label, (20, 130))
        self.preset_name_input = TextInputBox(20, 150, 250, 30, self.font_small)
        self.save_preset_button = Button(290, 150, 95, 30, "Save Preset", self.save_current_preset)
        self.delete_preset_button = Button(395, 150, 115, 30, "Delete Preset", self.delete_selected_preset)
        
        self.vis_rect = pygame.Rect(WINDOW_WIDTH - 330, 80, 310, WINDOW_HEIGHT - 240)
        
        button_y = self.vis_rect.bottom + 20
        button_width = 130
        gap = 10
        total_width = button_width * 2 + gap
        start_x = self.vis_rect.x + (self.vis_rect.width - total_width) // 2
        
        self.start_button = Button(start_x, button_y, button_width, 50, "Start Session", self.start_session)
        self.stop_button = Button(start_x + button_width + gap, button_y, button_width, 50, "Stop Session", self.stop_session)
        self.stop_button.enabled = False

        slider_definitions = {
            'session_length': {"label": "Session Length (s)", "min": 10, "max": 3600, "step": 10},
            'peak_time': {"label": "Peak Time (s)", "min": 10, "max": 3600, "step": 10},
            'weak': {"label": "Weak Intensity", "min": 10, "max": 255, "step": 5},
            'strong': {"label": "Strong Intensity", "min": 10, "max": 255, "step": 5},
            'max': {"label": "Max Intensity", "min": 10, "max": 255, "step": 5},
            'buzz_min': {"label": "Min Buzz (ms)", "min": 50, "max": 1000, "step": 10},
            'buzz_max': {"label": "Max Buzz (ms)", "min": 100, "max": 3000, "step": 50},
            'gap_min': {"label": "Min Gap (ms)", "min": 50, "max": 1000, "step": 10},
            'max_gap': {"label": "Max Gap (ms)", "min": 100, "max": 3000, "step": 50},
            'alternation_bias': {"label": "Alt. Bias", "min": 0.0, "max": 1.0, "step": 0.05},
            'variance': {"label": "Variance", "min": 0.0, "max": 0.5, "step": 0.01},
            'breathing_amount': {"label": "Breathing Amt", "min": 0.0, "max": 0.3, "step": 0.01},
            'breathing_period': {"label": "Breathing Period", "min": 5.0, "max": 30.0, "step": 1.0},
            'trigger_delay': {"label": "Trigger Delay", "min": 0.1, "max": 2.0, "step": 0.1},
            'trigger_intensity': {"label": "Trigger Int.", "min": 0.1, "max": 1.0, "step": 0.05},
            'resonance_probability': {"label": "Resonance Prob", "min": 0.0, "max": 0.5, "step": 0.01},
            'resonance_frequency': {"label": "Resonance Freq", "min": 0.5, "max": 5.0, "step": 0.1},
            'resonance_intensity': {"label": "Resonance Int.", "min": 0.1, "max": 2.0, "step": 0.1},
            'resonance_duration_min': {"label": "Res. Min Dur", "min": 1.0, "max": 10.0, "step": 0.5},
            'resonance_duration_max': {"label": "Res. Max Dur", "min": 2.0, "max": 15.0, "step": 0.5},
            'breathing_pulse_period': {"label": "Breathing Period (s)", "min": 2.0, "max": 30.0, "step": 0.5},
            'breathing_pulse_sync_period': {"label": "Sync Period (s)", "min": 10.0, "max": 120.0, "step": 1.0},
            'breathing_pulse_min_intensity': {"label": "Min Intensity", "min": 10, "max": 255, "step": 5},
            'breathing_pulse_cycles': {"label": "Cycles Before Gap", "min": 1, "max": 10, "step": 1},
            'breathing_pulse_gap': {"label": "Gap Duration (s)", "min": 0.0, "max": 10.0, "step": 0.5},
        }

        col1_x = 20
        col2_x = 520
        full_width = 450
        half_width = 215
        third_width = 130

        layout_map = [
            # Column 1
            {"title": "Basic Settings", "col": col1_x, "sliders": [("session_length", full_width)]},
            {"title": "", "col": col1_x, "sliders": [("peak_time", full_width)]},
            {"title": "Intensity Levels", "col": col1_x, "sliders": [("weak", third_width), ("strong", third_width), ("max", third_width)]},
            {"title": "Stochastic Timing", "col": col1_x, "sliders": [("buzz_min", half_width), ("buzz_max", half_width)]},
            {"title": "Stochastic Gaps", "col": col1_x, "sliders": [("gap_min", half_width), ("max_gap", half_width)]},
            
            # Column 2
            {"title": "Stochastic Behavior", "col": col2_x, "sliders": [("alternation_bias", half_width), ("variance", half_width)]},
            {"title": "Stochastic Advanced Effects", "col": col2_x, "sliders": [("breathing_amount", half_width), ("breathing_period", half_width)]},
            {"title": "Stochastic Triggers", "col": col2_x, "sliders": [("trigger_delay", half_width), ("trigger_intensity", half_width)]},
            {"title": "Stochastic Resonance", "col": col2_x, "sliders": [("resonance_probability", half_width), ("resonance_frequency", half_width)]},
            
            {"title": "Breathing Pulse Settings", "col": col2_x, "sliders": [("breathing_pulse_min_intensity", half_width), ("breathing_pulse_period", half_width)]},
            {"title": "Breathing Pulse Sync & Cycles", "col": col2_x, "sliders": [("breathing_pulse_sync_period", half_width), ("breathing_pulse_cycles", half_width)]},
            {"title": "Breathing Pulse Gaps", "col": col2_x, "sliders": [("breathing_pulse_gap", full_width)]},
        ]

        current_y = 200
        section_padding = 35
        slider_row_height = 60
        
        y_positions = {}
        for section in layout_map:
            col = section["col"]
            y = y_positions.get(col, current_y)
            self.sections.append((section["title"], col, y))
            y += section_padding
            
            x_pos = col
            for key, width in section["sliders"]:
                if key not in slider_definitions: continue
                defs = slider_definitions[key]
                self.sliders[key] = Slider(x_pos, y, width, defs["label"], defs["min"], defs["max"], self.config[key], defs["step"])
                x_pos += width + 20
            
            y += slider_row_height
            y_positions[col] = y

    def apply_preset(self, preset_name: str):
        """Apply a preset configuration."""
        if preset_name == 'Custom': return
        presets = self.preset_manager.get_all_presets()
        if preset_name in presets:
            preset = presets[preset_name]
            default = self.preset_manager.get_default_config()
            for key in default:
                value_to_apply = preset.get(key, default[key])
                self.config[key] = value_to_apply
                if key in self.sliders:
                    self.sliders[key].value = value_to_apply
            
            mode_to_set = None
            if preset_name == 'Cycle':
                mode_to_set = 'cycle'
            elif preset_name == 'Breathing Pulse':
                mode_to_set = 'breathing_pulse'
            
            if mode_to_set:
                try:
                    mode_index = self.mode_dropdown.options.index(mode_to_set)
                    self.mode_dropdown.selected_index = mode_index
                except ValueError:
                    pass
    
    def _refresh_preset_dropdown(self):
        """Reloads the preset dropdown with the latest presets."""
        all_presets = self.preset_manager.get_all_presets()
        self.preset_dropdown.options = ['Custom'] + list(all_presets.keys())
        self.preset_dropdown.selected_index = 0

    def save_current_preset(self):
        """Saves the current slider values as a new preset."""
        name = self.preset_name_input.text.strip()
        if not name or name == "Custom":
            print("[WARN] Invalid preset name.")
            return
        
        current_config = {key: slider.value for key, slider in self.sliders.items()}
        self.preset_manager.save_preset(name, current_config)
        self._refresh_preset_dropdown()
        
        if name in self.preset_dropdown.options:
            self.preset_dropdown.selected_index = self.preset_dropdown.options.index(name)
        
        self.preset_name_input.text = ""
        print(f"[INFO] Preset '{name}' saved.")

    def delete_selected_preset(self):
        """Deletes the currently selected custom preset."""
        name = self.preset_dropdown.get_selected()
        if self.preset_manager.is_custom_preset(name):
            self.preset_manager.delete_preset(name)
            self._refresh_preset_dropdown()
            print(f"[INFO] Preset '{name}' deleted.")
        else:
            print(f"[WARN] Cannot delete a default preset.")
    
    def update_config_from_ui(self):
        """Update config from UI elements."""
        for key, slider in self.sliders.items():
            self.config[key] = slider.value
        self.config['mode'] = self.mode_dropdown.get_selected()
    
    def start_session(self):
        """Start vibration session."""
        if self.session_active: return
        if not self.controller_connected: return
        
        self.update_config_from_ui()
        self.session_active = True
        self.session_completed_flag = False
        self.start_button.enabled = False
        self.stop_button.enabled = True
        self.session_start_time = time.time()
        
        self.session_thread = threading.Thread(target=self.run_session, daemon=True)
        self.session_thread.start()
    
    def stop_session(self):
        """Stop vibration session."""
        if not self.session_active: return
        self.session_active = False
        self.stop_button.enabled = False
    
    def _handle_session_end(self):
        """Thread-safe method to clean up after a session ends."""
        self.session_completed_flag = False
        self.start_button.enabled = True
        self.stop_button.enabled = False
        self.start_button.hovered = False
        self.stop_button.hovered = False
        self.session_thread = None
        self.current_left = 0.0
        self.current_right = 0.0

    def run_session(self):
        """Run vibration session (in separate thread)."""
        self.pattern_gen = HapticPatternGenerator(self.config)
        self.pattern_gen.start()
        last_update = time.time()
        
        while self.session_active:
            current = time.time()
            dt = current - last_update
            last_update = current
            
            elapsed = current - self.session_start_time
            if elapsed >= self.config['session_length']:
                self.session_active = False
                break
            
            left, right = 0.0, 0.0
            
            if self.config['mode'] == 'stochastic':
                left, right = self.pattern_gen.update_stochastic(dt)
            elif self.config['mode'] == 'breathing_pulse':
                left, right = self.pattern_gen.update_breathing_pulse(dt)
            elif self.config['mode'] == 'cycle':
                left, right = self.pattern_gen.update_cycle_pulse(dt)
            else: # All other constant modes
                left, right = self.pattern_gen.update_constant_pulse(dt, self.config['mode'])
            
            time_remaining = self.config['session_length'] - elapsed
            if time_remaining < (FADEOUT_MS / 1000.0):
                fade_mult = time_remaining / (FADEOUT_MS / 1000.0)
                left *= fade_mult
                right *= fade_mult
            
            self.current_left = left
            self.current_right = right
            self.controller.set_rumble(left, right)
            time.sleep(UPDATE_INTERVAL_MS / 1000.0)
        
        self.controller.stop()
        self.session_completed_flag = True

    def draw_header(self):
        """Draw header section."""
        title = self.font_large.render("Wave2Joy", True, ACCENT_COLOR)
        self.screen.blit(title, (20, 20))
        
        status_text = f"Controller: {self.controller.get_name()}"
        status_color = ACTIVE_COLOR if self.controller_connected else WARNING_COLOR
        status = self.font_small.render(status_text, True, status_color)
        self.screen.blit(status, (WINDOW_WIDTH - 340, 25))
        
        if self.session_active:
            elapsed = time.time() - self.session_start_time
            remaining = max(0, self.config['session_length'] - elapsed)
            time_text = f"Time: {int(elapsed)}s / {int(self.config['session_length'])}s ({int(remaining)}s left)"
            time_surf = self.font_small.render(time_text, True, ACTIVE_COLOR)
            self.screen.blit(time_surf, (20, 185))
    
    def draw_visualizer(self):
        """Draw real-time visualization."""
        pygame.draw.rect(self.screen, PANEL_COLOR, self.vis_rect, border_radius=10)
        pygame.draw.rect(self.screen, ACCENT_COLOR, self.vis_rect, 2, border_radius=10)
        
        vis_title = self.font_medium.render("Live Output", True, TEXT_COLOR)
        self.screen.blit(vis_title, (self.vis_rect.x + 20, 95))
        
        left_label = self.font_small.render("Left Motor (Low Freq)", True, TEXT_COLOR)
        self.screen.blit(left_label, (self.vis_rect.x + 20, 140))
        left_bar_rect = pygame.Rect(self.vis_rect.x + 20, 165, 270, 40)
        pygame.draw.rect(self.screen, SLIDER_COLOR, left_bar_rect, border_radius=5)
        if self.current_left > 0:
            left_fill = pygame.Rect(left_bar_rect.x, 165, int(270 * self.current_left / 255), 40)
            pygame.draw.rect(self.screen, ACTIVE_COLOR, left_fill, border_radius=5)
        left_value = self.font_small.render(f"{int(self.current_left)}", True, TEXT_COLOR)
        self.screen.blit(left_value, (left_bar_rect.right + 10, 172))
        
        right_label = self.font_small.render("Right Motor (High Freq)", True, TEXT_COLOR)
        self.screen.blit(right_label, (self.vis_rect.x + 20, 230))
        right_bar_rect = pygame.Rect(self.vis_rect.x + 20, 255, 270, 40)
        pygame.draw.rect(self.screen, SLIDER_COLOR, right_bar_rect, border_radius=5)
        if self.current_right > 0:
            right_fill = pygame.Rect(right_bar_rect.x, 255, int(270 * self.current_right / 255), 40)
            pygame.draw.rect(self.screen, (100, 200, 255), right_fill, border_radius=5)
        right_value = self.font_small.render(f"{int(self.current_right)}", True, TEXT_COLOR)
        self.screen.blit(right_value, (right_bar_rect.right + 10, 262))
        
        if self.session_active and self.pattern_gen and self.config['mode'] == 'stochastic':
            info_y = 320
            phase_text = f"Phase: {self.pattern_gen.current_phase.upper()}"
            self.screen.blit(self.font_small.render(phase_text, True, TEXT_COLOR), (self.vis_rect.x + 20, info_y))
            motor_text = f"Active: {self.pattern_gen.next_motor.upper() if self.pattern_gen.next_motor else 'None'}"
            self.screen.blit(self.font_small.render(motor_text, True, TEXT_COLOR), (self.vis_rect.x + 20, info_y + 25))
            if self.pattern_gen.resonance_mode:
                res_text = f"Resonance: {self.pattern_gen.resonance_mode.replace('_', ' ').title()}"
                self.screen.blit(self.font_small.render(res_text, True, ACCENT_COLOR), (self.vis_rect.x + 20, info_y + 50))
            mult = self.pattern_gen.get_global_multiplier()
            mult_text = f"Intensity: {int(mult * 100)}%"
            self.screen.blit(self.font_small.render(mult_text, True, TEXT_COLOR), (self.vis_rect.x + 20, info_y + 75))
            progress = min(1.0, self.pattern_gen.current_time / self.config['peak_time']) if self.config['peak_time'] > 0 else 1.0
            prog_rect = pygame.Rect(self.vis_rect.x + 20, info_y + 110, 270, 20)
            pygame.draw.rect(self.screen, SLIDER_COLOR, prog_rect, border_radius=3)
            prog_fill = pygame.Rect(prog_rect.x, info_y + 110, int(270 * progress), 20)
            pygame.draw.rect(self.screen, ACCENT_COLOR, prog_fill, border_radius=3)
            self.screen.blit(self.font_small.render("Ramp Progress", True, TEXT_COLOR), (self.vis_rect.x + 20, info_y + 95))
        
        tips_y = self.vis_rect.bottom - 120
        tips = ["Tips:", "• Use presets for quick starts", "• Hover over settings for tooltips", "• Take breaks every 10-15 min", "• Adjust intensity for comfort"]
        for i, tip in enumerate(tips):
            tip_surf = self.font_small.render(tip, True, TEXT_COLOR if i == 0 else (150, 150, 160))
            self.screen.blit(tip_surf, (self.vis_rect.x + 20, tips_y + i * 20))
    
    def draw_sections(self):
        """Draw configuration sections."""
        for label, x, y in self.sections:
            if label: # Don't draw title for empty-titled sections
                text = self.font_small.render(label, True, ACCENT_COLOR)
                self.screen.blit(text, (x, y))
                # --- CHANGE: Removed the underline drawing call ---
                # pygame.draw.line(self.screen, ACCENT_COLOR, (x, y + 22), (x + 450, y + 22), 1)
                # --- END CHANGE ---
    
    def on_mode_change(self):
        """Called when the mode dropdown is changed."""
        selected_mode = self.mode_dropdown.get_selected()
        if selected_mode.startswith('constant') or selected_mode == 'cycle' or selected_mode == 'breathing_pulse':
            self.sliders['session_length'].value = 3600
        else: # Stochastic mode
            default_len = self.preset_manager.get_default_config()['session_length']
            self.sliders['session_length'].value = default_len
        self.update_config_from_ui()

    def handle_events(self):
        """Handle pygame events."""
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                self.running = False
                return

            prev_mode_index = self.mode_dropdown.selected_index
            prev_preset_index = self.preset_dropdown.selected_index

            ui_elements = [self.preset_dropdown, self.mode_dropdown, self.start_button, self.stop_button, 
                           self.save_preset_button, self.delete_preset_button, self.preset_name_input] + list(self.sliders.values())

            event_handled = False
            for element in ui_elements:
                if element.handle_event(event):
                    event_handled = True
                    break 
            
            if self.mode_dropdown.selected_index != prev_mode_index:
                self.on_mode_change()
            
            if self.preset_dropdown.selected_index != prev_preset_index:
                current_preset = self.preset_dropdown.get_selected()
                if current_preset != 'Custom':
                    self.apply_preset(current_preset)
            
            if event.type == pygame.MOUSEBUTTONDOWN and not event_handled:
                if self.preset_dropdown.expanded: self.preset_dropdown.expanded = False
        
        mouse_pos = pygame.mouse.get_pos()
        self.active_tooltip_text = None
        
        all_ui_elements = list(self.sliders.items()) + [('preset', self.preset_dropdown), ('mode', self.mode_dropdown)]
        for key, element in all_ui_elements:
            if element.label_rect and element.label_rect.collidepoint(mouse_pos):
                self.active_tooltip_text = self.tooltips.get(key)
                break
        
        # Enable/disable delete button based on selection
        selected_preset = self.preset_dropdown.get_selected()
        self.delete_preset_button.enabled = self.preset_manager.is_custom_preset(selected_preset)

    def draw_tooltip(self):
        """Draws the active tooltip near the mouse cursor."""
        if not self.active_tooltip_text:
            return

        mouse_pos = pygame.mouse.get_pos()
        lines = self.active_tooltip_text.split('\n')
        
        surfaces = [self.font_small.render(line, True, TEXT_COLOR) for line in lines]
        
        max_width = max(s.get_width() for s in surfaces)
        total_height = sum(s.get_height() for s in surfaces)
        
        padding = 8
        box_rect = pygame.Rect(0, 0, max_width + padding * 2, total_height + padding * 2)
        
        box_rect.topleft = (mouse_pos[0] + 15, mouse_pos[1] + 10)
        if box_rect.right > WINDOW_WIDTH:
            box_rect.right = mouse_pos[0] - 15
        if box_rect.bottom > WINDOW_HEIGHT:
            box_rect.bottom = mouse_pos[1] - 10
            
        pygame.draw.rect(self.screen, PANEL_COLOR, box_rect, border_radius=4)
        pygame.draw.rect(self.screen, ACCENT_COLOR, box_rect, 1, border_radius=4)
        
        current_y = box_rect.y + padding
        for surf in surfaces:
            self.screen.blit(surf, (box_rect.x + padding, current_y))
            current_y += surf.get_height()

    def draw(self):
        """Draw all UI elements."""
        self.screen.fill(BG_COLOR)
        
        self.draw_header()
        self.draw_sections()
        
        for slider in self.sliders.values():
            slider.draw(self.screen, self.font_small)
        
        # Draw static preset UI first
        preset_name_label = self.font_small.render("Preset Name:", True, TEXT_COLOR)
        self.screen.blit(preset_name_label, (20, 130))
        self.preset_name_input.draw(self.screen)
        self.save_preset_button.draw(self.screen, self.font_small)
        self.delete_preset_button.draw(self.screen, self.font_small)
        
        # Draw dropdowns after other UI to ensure they render on top
        self.preset_dropdown.draw(self.screen, self.font_small)
        self.mode_dropdown.draw(self.screen, self.font_small)
        
        self.start_button.draw(self.screen, self.font_medium)
        self.stop_button.draw(self.screen, self.font_medium)
        
        self.draw_visualizer()
        
        self.draw_tooltip()
        
        pygame.display.flip()
    
    def run(self):
        """Main application loop."""
        while self.running:
            self.handle_events()
            
            if self.session_completed_flag:
                self._handle_session_end()

            self.draw()
            self.clock.tick(60)
        
        self.session_active = False
        if self.controller:
            self.controller.stop()
        pygame.quit()

# ============================================================================
# ENTRY POINT
# ============================================================================

def main():
    """Main entry point."""
    app = Wave2JoyGUI()
    app.run()

if __name__ == '__main__':
    main()
