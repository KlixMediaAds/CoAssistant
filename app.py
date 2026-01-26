import tkinter as tk
from tkinter import ttk, scrolledtext, font
import threading
import queue
import os
import sys
import time
import re
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI
from RealtimeSTT import AudioToTextRecorder

# --- CONFIGURATION ---
load_dotenv()
DEVICE_INDEX = int(os.getenv("DEVICE_INDEX", 1))
HISTORY_SIZE = 20

# --- COLOR PALETTE ---
COLORS = {
    "bg": "#1e1e1e",           
    "panel": "#252526",        
    "header": "#333333",       
    "accent": "#007acc",       
    "danger": "#d94444",       
    "text": "#ffffff",         
    "text_dim": "#cccccc",     
    "success": "#4ec9b0",
    "warning": "#d7ba7d"
}

# --- SYSTEM PROMPTS (SAFE MODE) ---
PROMPT_STRATEGY = """
CONTEXT: SALES TRAINING SIMULATION.
ROLE: Sales Coach.
GOAL: Guide the user to close the deal.
OUTPUT FORMAT: [CUE]: "Ask about X" or "Pivot to Y".
"""

PROMPT_SCRIPT = """
CONTEXT: SALES TRAINING SIMULATION.
ROLE: Dialogue Assistant.
GOAL: Provide the exact lines for the user to practice.
STRICT RULE: DO NOT GIVE INSTRUCTIONS. Just the line.
OUTPUT FORMAT: [CUE]: "Your exact line here."
"""

BASE_SYSTEM_PROMPT = """
INPUT:
1. SCENARIO: {mission}
2. TRANSCRIPT: {history}
3. LATEST: {text}

TASK:
1. Analyze the conversation.
2. EXTRACT DATA: [DATA]: KEY=VALUE
3. PROVIDE CUE: [CUE]: Your advice.
"""

class ModernHUD(tk.Tk):
    def __init__(self, recorder):
        super().__init__()
        
        self.recorder = recorder
        self.title("KlixOS - Enterprise Orchestrator")
        self.geometry("1200x800")
        self.configure(bg=COLORS["bg"])

        # State
        self.transcript_history = []
        self.mission_context = "NO MISSION SELECTED"
        self.cue_mode = "SCRIPT" 
        self.client = None
        self.gui_queue = queue.Queue()
        self.data_entries = {}

        # Fonts
        self.font_header = font.Font(family="Segoe UI", size=12, weight="bold")
        self.font_main = font.Font(family="Segoe UI", size=10)
        self.font_mono = font.Font(family="Consolas", size=10)
        self.font_cue = font.Font(family="Segoe UI", size=14, weight="bold")

        self._build_ui()
        self._init_openai()
        
        # Start Threads
        threading.Thread(target=self._audio_loop, daemon=True).start()
        self.after(50, self._process_queue) 
        
        # Bind Spacebar to Force Update
        self.bind('<space>', lambda e: self.force_ai_update(None))

    def _init_openai(self):
        key = os.getenv("OPENAI_API_KEY")
        if key: 
            self.client = OpenAI(api_key=key)
            print("DEBUG: OpenAI Client Initialized.")
        else:
            self.gui_queue.put(("ai", "ERROR: NO OPENAI KEY FOUND IN .ENV"))

    def _audio_loop(self):
        print("DEBUG: Starting Audio Loop...")
        while True:
            try:
                text = self.recorder.text()
                if text.strip():
                    print(f"DEBUG: Heard '{text}'")
                    self.gui_queue.put(("final", text))
                    self._run_ai(text)
            except Exception as e:
                print(f"Loop Error: {e}")
                time.sleep(0.1)

    def _build_ui(self):
        # --- HEADER ---
        header = tk.Frame(self, bg=COLORS["header"], height=60, padx=10, pady=10)
        header.pack(fill="x")

        # Buttons load the SAFE scripts now
        self._btn(header, "SELL DRONES", "#2d4f2d", lambda: self.load_mission("mission_new.txt"), side="left")
        self._btn(header, "PITCH LEADS", "#2d2d4f", lambda: self.load_mission("mission_pitch_leads.txt"), side="left")
        
        self.lbl_status = tk.Label(header, text="SELECT MISSION", bg=COLORS["header"], fg=COLORS["text_dim"], font=self.font_header)
        self.lbl_status.pack(side="left", padx=20)
        
        self.lbl_ai_status = tk.Label(header, text="AI: IDLE", bg=COLORS["header"], fg=COLORS["text_dim"], font=("Segoe UI", 9))
        self.lbl_ai_status.pack(side="left", padx=10)

        self._btn(header, "RESET", COLORS["danger"], self.reset_session, side="right")
        self._btn(header, "FORCE CUE (Space)", COLORS["warning"], lambda: self.force_ai_update(None), side="right")
        
        self.btn_mode = tk.Button(header, text=f"MODE: {self.cue_mode}", bg=COLORS["accent"], fg="white", 
                                  font=self.font_header, relief="flat", padx=15, pady=5,
                                  command=self.toggle_mode)
        self.btn_mode.pack(side="right", padx=10)

        # --- BODY ---
        body = tk.Frame(self, bg=COLORS["bg"], padx=15, pady=15)
        body.pack(fill="both", expand=True)

        # Left Column
        left_col = tk.Frame(body, bg=COLORS["bg"])
        left_col.pack(side="left", fill="both", expand=True, padx=(0, 10))

        tk.Label(left_col, text="LIVE TRANSCRIPT", bg=COLORS["bg"], fg=COLORS["accent"], font=self.font_header).pack(anchor="w")
        self.txt_transcript = scrolledtext.ScrolledText(left_col, bg=COLORS["panel"], fg=COLORS["text_dim"], 
                                                        font=self.font_mono, insertbackground="white", relief="flat", height=12)
        self.txt_transcript.pack(fill="both", expand=True)

        # Cue Panel (With Scrollbar)
        self.frm_cue = tk.Frame(left_col, bg=COLORS["panel"], height=200, pady=10, padx=10)
        self.frm_cue.pack(fill="x", pady=(15, 0))
        self.frm_cue.pack_propagate(False)

        tk.Label(self.frm_cue, text="AI STRATEGY & CUES", bg=COLORS["panel"], fg=COLORS["accent"], font=("Segoe UI", 8)).pack(anchor="w")
        
        # Scrollbar Logic for Cues
        cue_scroll = ttk.Scrollbar(self.frm_cue)
        cue_scroll.pack(side="right", fill="y")

        self.txt_cue = tk.Text(self.frm_cue, bg=COLORS["panel"], fg="white", 
                               font=self.font_cue, wrap="word", relief="flat", height=5,
                               yscrollcommand=cue_scroll.set)
        self.txt_cue.pack(side="left", fill="both", expand=True)
        cue_scroll.config(command=self.txt_cue.yview)

        self.txt_cue.insert("1.0", "Select a Mission to start...\n")
        self.txt_cue.config(state="disabled")

        # Right Column
        right_col = tk.Frame(body, bg=COLORS["panel"], width=300, padx=15, pady=15)
        right_col.pack(side="right", fill="y")
        right_col.pack_propagate(False)

        tk.Label(right_col, text="EXTRACTED DATA", bg=COLORS["panel"], fg=COLORS["success"], font=self.font_header).pack(pady=(0, 20))
        for f in ["Name", "Phone", "Email", "Company", "Budget", "Pain Points"]:
            self._create_field(right_col, f)

    def _btn(self, parent, text, bg, cmd, side="left"):
        tk.Button(parent, text=text, bg=bg, fg="white", font=self.font_header, relief="flat", padx=15, pady=5, borderwidth=0, command=cmd).pack(side=side, padx=5)

    def _create_field(self, parent, label):
        tk.Label(parent, text=label.upper(), bg=COLORS["panel"], fg=COLORS["text_dim"], font=("Segoe UI", 8)).pack(anchor="w")
        entry = tk.Entry(parent, bg="#3c3c3c", fg="white", font=self.font_main, relief="flat", insertbackground="white")
        entry.pack(fill="x", pady=(2, 15), ipady=5)
        self.data_entries[label] = entry

    def toggle_mode(self):
        self.cue_mode = "SCRIPT" if self.cue_mode == "STRATEGY" else "STRATEGY"
        color = "#d98c25" if self.cue_mode == "SCRIPT" else COLORS["accent"]
        self.btn_mode.config(text=f"MODE: {self.cue_mode}", bg=color)
        if self.transcript_history:
             self.force_ai_update(None, self.transcript_history[-1])

    def load_mission(self, filename):
        if os.path.exists(filename):
            self.reset_session()
            with open(filename, "r", encoding="utf-8") as f: self.mission_context = f.read()
            self.lbl_status.config(text=f"ACTIVE: {filename.replace('mission_', '').replace('.txt', '').upper()}", fg=COLORS["success"])
            
            print(f"[DEBUG] LOADED MISSION FILE: {filename}")
            
            # --- INSTANT OPENER ---
            opener = "Select Mission to see opener..."
            if "mission_new" in filename or "pitch_leads" in filename:
                opener = '"Hello, this is Josh from Kolasa Ag Systems. I have two active files on my desk—farmers looking to purchase DJI T50s immediately. Do you have stock?"'
                # PRE-LOAD MEMORY: Tell the AI we already said this!
                self.transcript_history.append(f"[ME]: {opener}")
            
            self._update_cue(opener)
        else:
            print(f"ERROR: Could not find {filename}")

    def reset_session(self):
        self.transcript_history = []
        self.mission_context = "NO MISSION SELECTED"
        self.txt_transcript.delete(1.0, tk.END)
        self.txt_cue.config(state="normal")
        self.txt_cue.delete("1.0", tk.END)
        self.txt_cue.insert("1.0", "Select a Mission to start...\n")
        self.txt_cue.config(state="disabled")
        for e in self.data_entries.values(): e.delete(0, tk.END)

    def force_ai_update(self, event, override_text=None):
        context_text = override_text if override_text else "USER REQUESTS IMMEDIATE ADVICE."
        threading.Thread(target=self._run_ai, args=(context_text,), daemon=True).start()

    def _run_ai(self, text):
        if not self.client: return
        
        if self.mission_context == "NO MISSION SELECTED":
            print("DEBUG: No mission selected. Ignoring input.")
            self.gui_queue.put(("ai", "[CUE]: PLEASE SELECT A MISSION FROM THE TOP MENU."))
            return

        if len(text) < 5 and "USER REQUESTS" not in text and "Session Started" not in text: return

        self.gui_queue.put(("status", "ANALYZING..."))
        
        # 1. Add THE OTHER PERSON's text to history
        if "USER REQUESTS" not in text and "Session Started" not in text and text not in self.transcript_history:
            self.transcript_history.append(f"[THEM]: {text}")
            if len(self.transcript_history) > HISTORY_SIZE: self.transcript_history.pop(0)

        temp = 0.7 if self.cue_mode == "SCRIPT" else 0.5
        persona = PROMPT_SCRIPT if self.cue_mode == "SCRIPT" else PROMPT_STRATEGY
        system_msg = f"{persona}\n{BASE_SYSTEM_PROMPT.format(mission=self.mission_context, history=chr(10).join(self.transcript_history), text=text)}"

        try:
            print("DEBUG: Sending to AI...")
            response = self.client.chat.completions.create(
                model="gpt-4o", messages=[{"role": "system", "content": system_msg}], temperature=temp, max_tokens=150
            )
            content = response.choices[0].message.content.strip()
            print(f"DEBUG AI: {content}")
            
            # 2. Add MY (AI's) text to history so we remember we said it
            clean_cue = content
            if "[CUE]:" in content:
                clean_cue = content.split("[CUE]:")[1].split("|")[0].strip().strip('"')
            
            self.transcript_history.append(f"[ME]: {clean_cue}")
            
            self.gui_queue.put(("ai", content))
        except Exception as e:
            print(f"AI ERROR: {e}")
            self.gui_queue.put(("ai", f"API ERROR: {e}"))
        self.gui_queue.put(("status", "IDLE"))

    def _process_queue(self):
        try:
            while True:
                msg_type, content = self.gui_queue.get_nowait()
                if msg_type == "final":
                    self.txt_transcript.insert(tk.END, f"\n{content}")
                    self.txt_transcript.see(tk.END)
                elif msg_type == "ai":
                    self._parse_ai(content)
                elif msg_type == "status":
                    self.lbl_ai_status.config(text=f"AI: {content}", fg=COLORS["warning"] if content == "ANALYZING..." else COLORS["text_dim"])
        except queue.Empty: pass
        self.after(50, self._process_queue)

    def _update_cue(self, text):
        timestamp = datetime.now().strftime("%H:%M:%S")
        self.txt_cue.config(state="normal")
        self.txt_cue.insert(tk.END, f"\n[{timestamp}] {text}\n")
        self.txt_cue.see(tk.END)
        self.txt_cue.config(state="disabled")

    def _parse_ai(self, text):
        if "[DATA]:" in text:
            raw_data = text.split("[DATA]:")[1].strip()
            parts = re.split(r'[,\n]', raw_data)
            for part in parts:
                if "=" in part:
                    try:
                        k, v = part.split("=", 1)
                        k, v = k.strip(), v.split("|")[0].strip()
                        for field_key in self.data_entries:
                            if k.upper() in field_key.upper() or field_key.upper() in k.upper():
                                self.data_entries[field_key].delete(0, tk.END)
                                self.data_entries[field_key].insert(0, v)
                    except: pass

        clean_cue = ""
        if "[CUE]:" in text:
            clean_cue = text.split("[CUE]:")[1].split("|")[0].strip().strip('"')
        elif not "[DATA]:" in text: 
            clean_cue = text
        if clean_cue:
            self._update_cue(clean_cue)

def main():
    print("------------------------------------------------")
    print(" SYSTEM BOOT: INITIALIZING AUDIO ENGINE")
    print("------------------------------------------------")
    try:
        recorder = AudioToTextRecorder(
            model="tiny", language="en", spinner=False, enable_realtime_transcription=True,
            input_device_index=DEVICE_INDEX, silero_sensitivity=0.05, webrtc_sensitivity=1, post_speech_silence_duration=0.6,
        )
        print("✅ AUDIO ENGINE READY.")
        app = ModernHUD(recorder)
        app.mainloop()
    except KeyboardInterrupt: print("Shutting down...")
    except Exception as e: print(f"CRITICAL STARTUP ERROR: {e}")

if __name__ == "__main__":
    main()
