import os
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
import tkinter as tk
from tkinter import ttk, font, simpledialog, messagebox
import threading
import queue
import os
import time
import re
from datetime import datetime
from dotenv import load_dotenv
from openai import OpenAI
from RealtimeSTT import AudioToTextRecorder
import styles
import backend  # <--- IMPORTING YOUR ENGINE

# --- CONFIGURATION ---
load_dotenv()
HISTORY_SIZE = 20
LOG_DIR = "logs"

if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# --- CUSTOM DIALOGS ---
class SaveLeadDialog(tk.Toplevel):
    def __init__(self, parent, default_name, default_email, callback):
        super().__init__(parent)
        self.callback = callback
        self.title("Save Lead Data")
        self.geometry("400x350")
        self.config(bg="#1e1e1e")
        self.transient(parent)
        self.grab_set()
        
        x = parent.winfo_x() + (parent.winfo_width() // 2) - 200
        y = parent.winfo_y() + (parent.winfo_height() // 2) - 175
        self.geometry(f"+{x}+{y}")

        lbl_style = {"bg": "#1e1e1e", "fg": "white", "font": ("Segoe UI", 10)}
        entry_bg = "#333333"
        entry_fg = "white"

        tk.Label(self, text="LEAD NAME / BUSINESS", **lbl_style).pack(anchor="w", padx=20, pady=(20, 5))
        self.ent_name = tk.Entry(self, bg=entry_bg, fg=entry_fg, relief="flat", font=("Segoe UI", 11))
        self.ent_name.pack(fill="x", padx=20)
        if default_name: self.ent_name.insert(0, default_name)

        tk.Label(self, text="EMAIL ADDRESS", **lbl_style).pack(anchor="w", padx=20, pady=(15, 5))
        self.ent_email = tk.Entry(self, bg=entry_bg, fg=entry_fg, relief="flat", font=("Segoe UI", 11))
        self.ent_email.pack(fill="x", padx=20)
        if default_email: self.ent_email.insert(0, default_email)

        tk.Label(self, text="OUTCOME", **lbl_style).pack(anchor="w", padx=20, pady=(15, 5))
        self.status_var = tk.StringVar(value="INTERESTED")
        self.cmb_status = ttk.Combobox(self, textvariable=self.status_var, values=["INTERESTED", "NOT INTERESTED", "CALLBACK", "CLOSED WON", "BAD DATA"], state="readonly")
        self.cmb_status.pack(fill="x", padx=20)

        btn_frame = tk.Frame(self, bg="#1e1e1e")
        btn_frame.pack(pady=30)
        tk.Button(btn_frame, text="CANCEL", bg="#555", fg="white", font=("Segoe UI", 10, "bold"), relief="flat", padx=15, pady=5, command=self.destroy).pack(side="left", padx=10)
        tk.Button(btn_frame, text="SAVE RECORD", bg="#4ec9b0", fg="white", font=("Segoe UI", 10, "bold"), relief="flat", padx=15, pady=5, command=self.save).pack(side="left", padx=10)
        self.ent_name.focus_set()

    def save(self):
        name = self.ent_name.get().strip()
        email = self.ent_email.get().strip()
        status = self.status_var.get()
        self.callback(name, email, status)
        self.destroy()

class ContextDialog(tk.Toplevel):
    def __init__(self, parent, current_text, callback):
        super().__init__(parent)
        self.callback = callback
        self.title("Mission Briefing / Context")
        self.geometry("600x400")
        self.config(bg="#1e1e1e")
        self.transient(parent)
        
        x = parent.winfo_x() + (parent.winfo_width() // 2) - 300
        y = parent.winfo_y() + (parent.winfo_height() // 2) - 200
        self.geometry(f"+{x}+{y}")

        tk.Label(self, text="PASTE LEAD DATA / WEBSITE INFO / NOTES:", bg="#1e1e1e", fg="#4ec9b0", font=("Segoe UI", 10, "bold")).pack(anchor="w", padx=20, pady=(20, 5))
        
        self.txt_input = tk.Text(self, bg="#333", fg="white", font=("Segoe UI", 10), height=15, relief="flat", padx=10, pady=10)
        self.txt_input.pack(fill="both", expand=True, padx=20, pady=5)
        self.txt_input.insert("1.0", current_text)

        btn_frame = tk.Frame(self, bg="#1e1e1e")
        btn_frame.pack(pady=20)
        tk.Button(btn_frame, text="CLEAR", bg="#d9534f", fg="white", font=("Segoe UI", 10), relief="flat", padx=15, pady=5, command=self.clear).pack(side="left", padx=10)
        tk.Button(btn_frame, text="SAVE CONTEXT", bg="#4ec9b0", fg="white", font=("Segoe UI", 10, "bold"), relief="flat", padx=15, pady=5, command=self.save).pack(side="left", padx=10)
        self.txt_input.focus_set()

    def clear(self):
        self.txt_input.delete("1.0", tk.END)

    def save(self):
        text = self.txt_input.get("1.0", tk.END).strip()
        self.callback(text)
        self.destroy()

# --- CUSTOM WIDGETS ---
class DarkScrolledText(tk.Frame):
    def __init__(self, parent, **kwargs):
        super().__init__(parent)
        self.scrollbar = ttk.Scrollbar(self, orient="vertical", style="Vertical.TScrollbar")
        self.scrollbar.pack(side="right", fill="y")
        if 'highlightthickness' in kwargs: del kwargs['highlightthickness']
        self.text = tk.Text(self, yscrollcommand=self.scrollbar.set, highlightthickness=1, relief="flat", **kwargs)
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
        self.lead_data_context = "" 
        
        self.client = None
        self.gui_queue = queue.Queue()

        self._init_fonts()
        self._init_styles()
        self._build_ui()
        self._init_openai_robust()
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
        
        self.btn_context = tk.Button(self.header, text="CONTEXT 📝", font=self.font_header, relief="flat", bg="#333", fg="white", padx=10, pady=5, command=self.open_context_dialog)
        self.btn_context.pack(side="left", padx=5)

        self.menu_missions = tk.Menu(self, tearoff=0)
        self.menu_missions.add_command(label="SELL DRONES", command=lambda: self.load_mission("mission_sell_drones.txt"))
        self.menu_missions.add_command(label="PITCH LEADS", command=lambda: self.load_mission("mission_pitch_leads.txt"))

        self.lbl_status = tk.Label(self.header, text="SELECT MISSION", font=self.font_header)
        self.lbl_status.pack(side="left", padx=20)
        
        self.btn_theme = tk.Button(self.header, text="☀️", bg=styles.SHARED["warning"], fg="white", font=("Segoe UI Emoji", 12), relief="flat", padx=10, pady=0, borderwidth=0, command=self.toggle_theme)
        self.btn_theme.pack(side="right", padx=5)
        self._btn(self.header, "SAVE DB", styles.SHARED["success"], self.open_save_dialog, side="right")
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
                widget.text.config(bg=palette["panel"], fg=palette["text"], insertbackground=palette["text"], highlightbackground=palette["border"], highlightcolor=palette["border"])
            self.btn_theme.config(text=palette["icon"])
            for lbl in [self.lbl_status, self.lbl_trans, self.lbl_cues]:
                bg_col = palette["header"] if lbl in self.header.winfo_children() else palette["bg"]
                if lbl == self.lbl_trans: bg_col = palette["bg"] 
                fg_col = styles.SHARED["accent"] if lbl in [self.lbl_trans, self.lbl_cues] else palette["text_dim"]
                if lbl.master == self.frm_transcript_container or lbl.master == self.frm_cues_container: bg_col = palette["bg"]
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
                inter_palette = {k: interpolate(start_colors[k], target[k], t) for k in target if target[k].startswith("#")}
                inter_palette["icon"] = target["icon"]
                inter_palette["menu_bg"] = target["menu_bg"]
                inter_palette["menu_fg"] = target["menu_fg"]
                update_colors(inter_palette)
                self.after(delay, lambda: step_anim(i+1))
            step_anim(0)

    def _init_openai_robust(self):
        if backend.ensure_api_key():
            self.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
            print("DEBUG: OpenAI Client Initialized.")
        else:
            print("CRITICAL ERROR: Still no API Key. AI features disabled.")
            self.gui_queue.put(("ai", "ERROR: NO API KEY. RESTART APP."))

    def _audio_loop(self):
        print("DEBUG: Audio Loop Started")
        while True:
            try:
                text = self.recorder.text()
                if text.strip():
                    print(f"\n[USER]: {text}") 
                    self.gui_queue.put(("final", text))
                    # --- THREADED AI CALL ---
                    threading.Thread(target=self._run_ai, args=(text,), daemon=True).start()
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
            
            if self.lead_data_context.strip():
                opener = "[AI ANALYZING DOSSIER FOR CUSTOM OPENER... PRESS SPACE]"
            else:
                opener = "Select Mission... (Or add Context)"
                if "sell_drones" in filename: opener = '"Hi, this is Josh from Kolasa Ag Systems..."'
            
            self._update_cue(opener)
            self.transcript_history.append(f"[ME]: {opener}")

    def open_context_dialog(self):
        ContextDialog(self, self.lead_data_context, self.save_context_data)

    def save_context_data(self, text):
        self.lead_data_context = text
        if text:
            self.btn_context.config(fg=styles.SHARED["success"], text="CONTEXT ✅")
        else:
            self.btn_context.config(fg="white", text="CONTEXT 📝")

    def reset_session(self):
        self.transcript_history = []
        self.unique_notes = set()
        self.mission_context = "NO MISSION SELECTED"
        self.cue_mode = "SCRIPT"
        self.btn_mode.config(text=f"MODE: {self.cue_mode}")
        self.txt_transcript.delete(1.0, tk.END)
        self.txt_cue.delete(1.0, tk.END); self.txt_cue.insert("1.0", "Select a Mission to start...\n")
        self.txt_notepad.delete("1.0", tk.END); self.txt_notepad.insert("1.0", "• Notes will appear here...\n")
        self.lead_data_context = ""
        self.btn_context.config(fg="white", text="CONTEXT 📝")

    def open_save_dialog(self):
        transcript = self.txt_transcript.get("1.0", tk.END).strip()
        if not transcript:
            messagebox.showinfo("Empty", "Nothing to save yet.")
            return
        found_email = ""
        found_name = ""
        for note in self.unique_notes:
            if "email:" in note.lower(): found_email = note.split(":", 1)[1].strip()
            if "name:" in note.lower() and "mission" not in note.lower(): found_name = note.split(":", 1)[1].strip()
        SaveLeadDialog(self, found_name, found_email, self.perform_db_save)

    def perform_db_save(self, name, email, status):
        transcript = self.txt_transcript.get("1.0", tk.END).strip()
        success, msg = backend.save_call_to_neon(self.active_mission_name, transcript, self.unique_notes, email, name, status)
        if success:
            self.lbl_status.config(text=f"SAVED: {name}", fg=styles.SHARED["success"])
            print(f"✅ DB SUCCESS: Saved lead '{name}' as '{status}'")
            self.after(3000, lambda: self.lbl_status.config(text=f"ACTIVE: {self.active_mission_name}"))
        else: messagebox.showerror("Database Error", msg)

    def on_close(self): self.destroy()

    def force_ai_update(self, event): threading.Thread(target=self._run_ai, args=("USER REQUESTS ADVICE",), daemon=True).start()

    def _update_cue(self, text):
        self.txt_cue.insert(tk.END, f"\n[{datetime.now().strftime('%H:%M:%S')}] ", "dim")
        self.txt_cue.insert(tk.END, f"{text}\n")
        self.txt_cue.see(tk.END)

    def _run_ai(self, text):
        if not self.client: return
        print(f"DEBUG: AI Called for input: '{text}'") 

        if self.mission_context == "NO MISSION SELECTED":
            print("⚠️ IGNORED: No Mission Selected.")
            self.gui_queue.put(("ai", "[CUE]: PLEASE SELECT A MISSION FROM THE MENU."))
            return

        self.gui_queue.put(("ai", "[ANALYZING...]"))
        self.transcript_history.append(f"[THEM]: {text}")
        if len(self.transcript_history) > HISTORY_SIZE: self.transcript_history.pop(0)

        # INJECT CONTEXT
        lead_data = self.lead_data_context if self.lead_data_context else "No prior context provided."
        
        # --- FIXED NAMESPACE REFERENCES HERE ---
        sys_msg = f"{backend.PROMPT_SCRIPT if self.cue_mode == 'SCRIPT' else backend.PROMPT_STRATEGY}\n{backend.BASE_SYSTEM_PROMPT.format(mission=self.mission_context, lead_data=lead_data, history=chr(10).join(self.transcript_history), text=text)}"
        
        try:
            resp = self.client.chat.completions.create(model="gpt-4o", messages=[{"role": "system", "content": sys_msg}], temperature=0.6)
            content = resp.choices[0].message.content.strip()
            print(f"[AI]: {content}\n")
            self.gui_queue.put(("ai", content))
        except Exception as e: 
            print(f"AI ERROR: {e}")
            self.gui_queue.put(("ai", f"ERROR: {e}"))

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
        if backend.ensure_api_key():
            mic_idx = backend.get_smart_mic_index()
            # FORCE int8 to avoid memory crash on Windows CPU
            recorder = AudioToTextRecorder(
                model="tiny", 
                language="en", 
                spinner=False, 
                enable_realtime_transcription=True, 
                input_device_index=mic_idx,
                compute_type="int8"
            )
            print("✅ AUDIO ENGINE READY.")
            ModernHUD(recorder).mainloop()
    except Exception as e: print(f"CRITICAL ERROR: {e}")
