import tkinter as tk
from tkinter import ttk, font
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
import styles

# --- CONFIGURATION ---
load_dotenv()
DEVICE_INDEX = int(os.getenv("DEVICE_INDEX", 1))
HISTORY_SIZE = 20
LOG_DIR = "logs"

if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# --- SYSTEM PROMPTS ---
PROMPT_STRATEGY = "CONTEXT: SALES SIMULATION. ROLE: Coach. OUTPUT: [CUE]: Advice."
PROMPT_SCRIPT = "CONTEXT: SALES SIMULATION. ROLE: Assistant. OUTPUT: [CUE]: Exact line."
BASE_SYSTEM_PROMPT = "ANALYZE: {mission}\nHISTORY: {history}\nINPUT: {text}\nTASK: Extract [NOTE]: Key: Value. Provide [CUE]: Advice."

# --- CUSTOM WIDGETS ---
class DarkScrolledText(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", style="Vertical.TScrollbar")
        self.scrollbar.pack(side="right", fill="y")
        
        if 'highlightthickness' in kwargs:
            del kwargs['highlightthickness']

        self.text = tk.Text(self, yscrollcommand=self.scrollbar.set, 
                            highlightthickness=1, 
                            relief="flat", 
                            **kwargs)
        self.text.pack(side="left", fill="both", expand=True)
        self.scrollbar.config(command=self.text.yview)
    
    def insert(self, *a): self.text.insert(*a)
    def delete(self, *a): self.text.delete(*a)
    def see(self, *a): self.text.see(*a)
    def get(self, *a): return self.text.get(*a)
    def tag_config(self, *a, **k): self.text.tag_config(*a, **k)
    def config(self, *a, **k): self.text.config(*a, **k)

class ModernHUD(tk.Tk):
    def __init__(self, recorder):
        super().__init__()
        self.recorder = recorder
        self.title("KlixOS - Enterprise Orchestrator")
        self.geometry("1200x800")
        
        self.current_theme = "dark"
        self.transcript_history = []
        self.active_mission_name = "NONE"
        self.mission_context = "NO MISSION SELECTED"
        self.cue_mode = "SCRIPT"
        self.unique_notes = set()
        
        self.client = None
        self.gui_queue = queue.Queue()

        self._init_fonts()
        self._init_styles()
        self._build_ui()
        self._init_openai()
        self.apply_theme("dark", animate=False) 

        threading.Thread(target=self._audio_loop, daemon=True).start()
        self.after(50, self._process_queue)
        self.bind('<space>', lambda e: self.force_ai_update(None))
        self.protocol("WM_DELETE_WINDOW", self.on_close)

    def _init_fonts(self):
        self.font_header = font.Font(family="Segoe UI", size=10, weight="bold")
        self.font_ui_text = font.Font(family="Segoe UI", size=11)
        self.font_mono = font.Font(family="Consolas", size=10)
        self.font_cue = font.Font(family="Segoe UI", size=14, weight="bold")
        self.font_timestamp = font.Font(family="Segoe UI", size=9)

    def _init_styles(self):
        self.style = ttk.Style()
        self.style.theme_use('clam')
        self.style.configure("Vertical.TScrollbar", gripcount=0, arrowsize=12)

    def _build_ui(self):
        self.header = tk.Frame(self, height=50, padx=10, pady=5)
        self.header.pack(fill="x")

        self.btn_missions = tk.Button(self.header, text="  MISSIONS ▾  ", font=self.font_header, relief="flat", padx=10, pady=5, command=self.show_mission_menu)
        self.btn_missions.pack(side="left", padx=5)
        
        self.menu_missions = tk.Menu(self, tearoff=0)
        self.menu_missions.add_command(label="SELL DRONES", command=lambda: self.load_mission("mission_sell_drones.txt"))
        self.menu_missions.add_command(label="PITCH LEADS", command=lambda: self.load_mission("mission_pitch_leads.txt"))

        self.lbl_status = tk.Label(self.header, text="SELECT MISSION", font=self.font_header)
        self.lbl_status.pack(side="left", padx=20)
        
        self.btn_theme = tk.Button(self.header, text="☀️", bg=styles.SHARED["warning"], fg="white", 
                                   font=("Segoe UI Emoji", 12), relief="flat", padx=10, pady=0, borderwidth=0, 
                                   command=self.toggle_theme)
        self.btn_theme.pack(side="right", padx=5)

        self._btn(self.header, "RESET", styles.SHARED["danger"], self.reset_session, side="right")
        self.btn_mode = tk.Button(self.header, text=f"MODE: {self.cue_mode}", font=self.font_header, relief="flat", padx=15, pady=2, command=self.toggle_mode)
        self.btn_mode.pack(side="right", padx=10)

        self.body = tk.Frame(self)
        self.body.pack(fill="both", expand=True)

        self.left_col = tk.Frame(self.body, padx=15, pady=15)
        self.left_col.pack(side="left", fill="both", expand=True)

        self.frm_transcript_container = tk.Frame(self.left_col, height=200) 
        self.frm_transcript_container.pack(side="bottom", fill="x", pady=(15, 0))
        self.frm_transcript_container.pack_propagate(False) 

        self.lbl_trans = tk.Label(self.frm_transcript_container, text="LIVE TRANSCRIPT", fg=styles.SHARED["accent"], font=("Segoe UI", 9, "bold"))
        self.lbl_trans.pack(anchor="w")
        
        self.txt_transcript = DarkScrolledText(self.frm_transcript_container, font=self.font_ui_text, height=12, padx=15, pady=10)
        self.txt_transcript.pack(fill="both", expand=True)

        self.frm_cues_container = tk.Frame(self.left_col)
        self.frm_cues_container.pack(side="top", fill="both", expand=True)
        
        self.lbl_cues = tk.Label(self.frm_cues_container, text="AI STRATEGY & CUES", fg=styles.SHARED["accent"], font=self.font_header)
        self.lbl_cues.pack(anchor="w", pady=(0, 5))
        
        self.txt_cue = DarkScrolledText(self.frm_cues_container, font=self.font_cue, padx=15, pady=15)
        self.txt_cue.pack(fill="both", expand=True)
        self.txt_cue.tag_config("dim", font=self.font_timestamp)

        self.right_col = tk.Frame(self.body, width=350, padx=10, pady=15)
        self.right_col.pack(side="right", fill="y")
        self.right_col.pack_propagate(False)
        
        tk.Label(self.right_col, text="LIVE NOTEPAD", fg=styles.SHARED["success"], font=self.font_header).pack(anchor="w", pady=(0, 10))
        self.txt_notepad = DarkScrolledText(self.right_col, font=self.font_mono, padx=10, pady=10)
        self.txt_notepad.pack(fill="both", expand=True)
        self.txt_notepad.insert("1.0", "• Notes will appear here...\n")

    def _btn(self, parent, text, bg, cmd, side="left"):
        tk.Button(parent, text=text, bg=bg, fg="white", font=self.font_header, relief="flat", padx=10, pady=2, borderwidth=0, command=cmd).pack(side=side, padx=5)

    def show_mission_menu(self):
        x = self.btn_missions.winfo_rootx()
        y = self.btn_missions.winfo_rooty() + self.btn_missions.winfo_height()
        self.menu_missions.post(x, y)

    def toggle_theme(self):
        new_theme = "light" if self.current_theme == "dark" else "dark"
        self.apply_theme(new_theme, animate=True)

    def apply_theme(self, theme_name, animate=False):
        self.current_theme = theme_name
        target = styles.THEMES[theme_name]
        
        def interpolate(c1, c2, t):
            r1, g1, b1 = int(c1[1:3],16), int(c1[3:5],16), int(c1[5:7],16)
            r2, g2, b2 = int(c2[1:3],16), int(c2[3:5],16), int(c2[5:7],16)
            r = int(r1 + (r2-r1)*t)
            g = int(g1 + (g2-g1)*t)
            b = int(b1 + (b2-b1)*t)
            return f"#{r:02x}{g:02x}{b:02x}"

        def update_colors(palette):
            self.configure(bg=palette["bg"])
            self.header.config(bg=palette["header"])
            self.body.config(bg=palette["bg"])
            self.left_col.config(bg=palette["bg"])
            
            for widget in [self.txt_transcript, self.txt_notepad, self.txt_cue]:
                widget.config(bg=palette["panel"]) 
                widget.text.config(bg=palette["panel"], fg=palette["text"], 
                                   insertbackground=palette["text"],
                                   highlightbackground=palette["border"], 
                                   highlightcolor=palette["border"])

            self.btn_theme.config(text=palette["icon"])

            for lbl in [self.lbl_status, self.lbl_trans, self.lbl_cues]:
                bg_col = palette["header"] if lbl in self.header.winfo_children() else palette["bg"]
                if lbl == self.lbl_trans: bg_col = palette["bg"] 
                
                fg_col = styles.SHARED["accent"] if lbl in [self.lbl_trans, self.lbl_cues] else palette["text_dim"]
                
                if lbl.master == self.frm_transcript_container or lbl.master == self.frm_cues_container:
                     bg_col = palette["bg"]

                lbl.config(bg=bg_col, fg=fg_col)

            self.frm_cues_container.config(bg=palette["bg"])
            self.frm_transcript_container.config(bg=palette["bg"])
            self.right_col.config(bg=palette["panel"])
            
            self.btn_missions.config(bg=styles.SHARED["accent"], fg="white")
            self.btn_mode.config(bg="#444", fg="white")
            self.menu_missions.config(bg=palette["menu_bg"], fg=palette["menu_fg"])
            self.style.configure("Vertical.TScrollbar", background=palette["scroll_fg"], troughcolor=palette["scroll_bg"], bordercolor=palette["scroll_bg"])
            self.txt_cue.tag_config("dim", foreground=palette["text_dim"])
            self.txt_notepad.tag_config("key_bold", foreground=styles.SHARED["key_highlight"] if theme_name == "dark" else "#0055bb")

        if not animate:
            update_colors(target)
        else:
            steps = 10; delay = 20
            start_colors = styles.THEMES["light" if theme_name == "dark" else "dark"]
            def step_anim(i):
                if i > steps: return
                t = i / steps
                # FIX: Check if VALUE starts with '#' instead of KEY
                inter_palette = {k: interpolate(start_colors[k], target[k], t) for k in target if target[k].startswith("#")}
                inter_palette["icon"] = target["icon"]
                inter_palette["menu_bg"] = target["menu_bg"]
                inter_palette["menu_fg"] = target["menu_fg"]
                update_colors(inter_palette)
                self.after(delay, lambda: step_anim(i+1))
            step_anim(0)

    def _init_openai(self):
        key = os.getenv("OPENAI_API_KEY")
        if key: self.client = OpenAI(api_key=key)

    def _audio_loop(self):
        print("DEBUG: Audio Loop Started")
        while True:
            try:
                text = self.recorder.text()
                if text.strip():
                    print(f"\n[USER]: {text}") 
                    self.gui_queue.put(("final", text))
                    self._run_ai(text)
            except: time.sleep(0.1)

    def _process_queue(self):
        try:
            while True:
                msg, content = self.gui_queue.get_nowait()
                if msg == "final": 
                    self.txt_transcript.insert(tk.END, f"\n{content}")
                    self.txt_transcript.see(tk.END)
                elif msg == "ai": self._parse_ai(content)
        except queue.Empty: pass
        self.after(50, self._process_queue)

    def toggle_mode(self):
        self.cue_mode = "SCRIPT" if self.cue_mode == "STRATEGY" else "STRATEGY"
        self.btn_mode.config(text=f"MODE: {self.cue_mode}")

    def load_mission(self, filename):
        if os.path.exists(filename):
            self.reset_session()
            self.active_mission_name = filename.replace('mission_', '').replace('.txt', '').upper()
            with open(filename, "r", encoding="utf-8") as f: self.mission_context = f.read()
            self.lbl_status.config(text=f"ACTIVE: {self.active_mission_name}", fg=styles.SHARED["success"])
            
            opener = "Select Mission..."
            if "sell_drones" in filename: opener = '"Hi, this is Josh from Kolasa Ag Systems..."'
            elif "pitch_leads" in filename: opener = '"Hello, this is Josh from Kolasa Ag Systems..."'
            
            self._update_cue(opener)
            self.transcript_history.append(f"[ME]: {opener}")

    def reset_session(self):
        self.transcript_history = []
        self.unique_notes = set()
        self.mission_context = "NO MISSION SELECTED"
        self.txt_transcript.delete(1.0, tk.END)
        self.txt_cue.delete(1.0, tk.END); self.txt_cue.insert("1.0", "Select a Mission to start...\n")
        self.txt_notepad.delete("1.0", tk.END); self.txt_notepad.insert("1.0", "• Notes will appear here...\n")

    def on_close(self): self.destroy()

    def force_ai_update(self, event): threading.Thread(target=self._run_ai, args=("USER REQUESTS ADVICE",), daemon=True).start()

    def _update_cue(self, text):
        self.txt_cue.insert(tk.END, f"\n[{datetime.now().strftime('%H:%M:%S')}] ", "dim")
        self.txt_cue.insert(tk.END, f"{text}\n")
        self.txt_cue.see(tk.END)

    def _run_ai(self, text):
        if not self.client: return
        self.gui_queue.put(("ai", "[ANALYZING...]"))
        
        self.transcript_history.append(f"[THEM]: {text}")
        if len(self.transcript_history) > HISTORY_SIZE: self.transcript_history.pop(0)

        sys_msg = f"{PROMPT_SCRIPT if self.cue_mode == 'SCRIPT' else PROMPT_STRATEGY}\n{BASE_SYSTEM_PROMPT.format(mission=self.mission_context, history=chr(10).join(self.transcript_history), text=text)}"
        
        try:
            resp = self.client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": sys_msg}], temperature=0.6)
            content = resp.choices[0].message.content.strip()
            print(f"[AI]: {content}\n")
            self.gui_queue.put(("ai", content))
        except Exception as e: self.gui_queue.put(("ai", f"ERROR: {e}"))

    def _parse_ai(self, text):
        if "[NOTE]:" in text:
            raw = text.split("[NOTE]:")[1].split("[CUE]")[0].strip()
            for line in raw.split('\n'):
                clean = re.sub(r'\W+', '', line).lower()
                if line and not any(re.sub(r'\W+', '', x).lower() == clean for x in self.unique_notes):
                    self.unique_notes.add(line)
                    if ":" in line:
                        k, v = line.split(":", 1)
                        self.txt_notepad.insert(tk.END, "• "); self.txt_notepad.insert(tk.END, f"{k}:", "key_bold"); self.txt_notepad.insert(tk.END, f"{v}\n")
                    else: self.txt_notepad.insert(tk.END, f"• {line}\n")
                    self.txt_notepad.see(tk.END)
        
        if "[CUE]:" in text:
            self._update_cue(text.split("[CUE]:")[1].split("|")[0].strip().strip('"'))

if __name__ == "__main__":
    try:
        recorder = AudioToTextRecorder(model="tiny", language="en", spinner=False, enable_realtime_transcription=True, input_device_index=DEVICE_INDEX)
        print("✅ AUDIO ENGINE READY.")
        ModernHUD(recorder).mainloop()
    except Exception as e: print(f"CRITICAL ERROR: {e}")
