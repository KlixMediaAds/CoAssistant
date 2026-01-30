import os
import pyaudio
import psycopg2
import tkinter as tk
from tkinter import simpledialog

# --- SYSTEM PROMPTS (THE BLENDER) ---

# STRATEGY MODE: Coaches you on the logic
PROMPT_STRATEGY = (
    "CONTEXT: SALES SIMULATION. ROLE: Coach.\n"
    "OBJECTIVE: Guide the user to execute the MISSION using the CONTEXT.\n"
    "LOGIC FLOW:\n"
    "1. ANALYZE context. If the Mission targets Dealers, do not use Farmer logic.\n"
    "2. LISTEN to the user. If they are stuck, give a strategic pivot.\n"
    "3. OUTPUT: [CUE]: A short, punchy strategic direction (e.g., 'He's hesitant on price. Pivot to the 'Commission' logic')."
)

# SCRIPT MODE: Writes the exact lines
# FIXED: Removed "Crop/Weather" hardcoding to allow for Dealer/B2B missions.
PROMPT_SCRIPT = (
    "CONTEXT: SALES SIMULATION. ROLE: Sales Copilot.\n"
    "OBJECTIVE: Generate the EXACT lines for the user to say to achieve the MISSION.\n"
    "CRITICAL INSTRUCTION: You must blend the MISSION (The Goal) with the CONTEXT (The Lead).\n"
    "INSTRUCTIONS:\n"
    "   1. Follow the 'STAGES' defined in the MISSION text explicitly.\n"
    "   2. Listen to the History. If the user has just spoken the Opener, move immediately to the next Stage (Pitch/Question).\n"
    "   3. If the user receives an objection, look for the 'IF' logic in the MISSION.\n"
    "   4. Use specific details from the CONTEXT (Name, Business) to personalize the script, but do not hallucinate crops/weather if they don't exist.\n"
    "OUTPUT FORMAT:\n"
    "1. [NOTE]: Key: Value (Extract new info).\n"
    "2. [CUE]: \"Exact words to say.\""
)

# Base Prompt injects the data
BASE_SYSTEM_PROMPT = (
    "--- MISSION (THE GOAL) ---\n{mission}\n\n"
    "--- CONTEXT (THE TARGET) ---\n{lead_data}\n\n"
    "--- CONVERSATION HISTORY ---\n{history}\n\n"
    "--- CURRENT INPUT ---\n{text}"
)

# --- PRE-FLIGHT CHECKS ---
def ensure_api_key():
    """Checks for API key at startup."""
    key = os.getenv("OPENAI_API_KEY")
    if not key:
        print("⚠️ API KEY MISSING: Launching Setup Wizard...")
        root = tk.Tk()
        root.withdraw()
        user_input = simpledialog.askstring("KlixOS Setup", "OpenAI API Key is missing.\n\nPlease paste it here:")
        root.destroy()
        
        if user_input and user_input.startswith("sk-"):
            with open(".env", "a") as f:
                f.write(f"\nOPENAI_API_KEY={user_input.strip()}")
            os.environ["OPENAI_API_KEY"] = user_input.strip()
            print("✅ SUCCESS: API Key saved.")
            return True
        else:
            print("❌ SETUP CANCELLED.")
            return False
    return True

def get_smart_mic_index():
    target_name = os.getenv("MIC_NAME", "Voicemeeter") 
    p = pyaudio.PyAudio()
    
    print(f"DEBUG: Searching for microphone matching '{target_name}'...")
    candidates = []
    
    for i in range(p.get_device_count()):
        try:
            info = p.get_device_info_by_index(i)
            if info['maxInputChannels'] > 0:
                name = info['name']
                if target_name.lower() in name.lower():
                    candidates.append((i, name))
        except: pass
    p.terminate()

    if not candidates:
        print("⚠️ No matching mic found. Using default index 1.")
        return 1

    best_index = candidates[0][0]
    best_name = candidates[0][1]

    for idx, name in candidates:
        if "B1" in name:
            best_index = idx
            best_name = name
            break
        elif "Output" in name and "Aux" not in name:
            best_index = idx
            best_name = name
    
    print(f"✅ AUTO-DETECT: Selected '{best_name}' at Index {best_index}")
    return best_index

# --- DATABASE ENGINE ---
def save_call_to_neon(mission, transcript, notes, client_email, client_name, status):
    db_url = os.getenv("DATABASE_URL")
    
    if not db_url:
        root = tk.Tk()
        root.withdraw()
        user_input = simpledialog.askstring("Database Setup", "Database URL is missing.\n\nPaste your NeonDB Connection String here:")
        root.destroy()
        if user_input and "postgres" in user_input:
            try:
                with open(".env", "a") as f: f.write(f"\nDATABASE_URL={user_input.strip()}")
                os.environ["DATABASE_URL"] = user_input.strip()
                db_url = user_input.strip()
            except Exception as e: return False, f"Could not save .env: {str(e)}"
        else: return False, "No Database URL provided."

    try:
        conn = psycopg2.connect(db_url)
        cur = conn.cursor()
        
        lead_id = None
        if client_email:
            cur.execute("SELECT id FROM leads WHERE email = %s", (client_email,))
            res = cur.fetchone()
            if res:
                lead_id = res[0]
                cur.execute("UPDATE leads SET name = %s, status = %s, updated_at = NOW() WHERE id = %s", (client_name, status, lead_id))
            else:
                cur.execute(
                    "INSERT INTO leads (name, email, status, created_at) VALUES (%s, %s, %s, NOW()) RETURNING id",
                    (client_name or "Unknown Lead", client_email, status)
                )
                lead_id = cur.fetchone()[0]
        else:
            cur.execute("INSERT INTO leads (name, status, created_at) VALUES ('Anonymous Caller', %s, NOW()) RETURNING id", (status,))
            lead_id = cur.fetchone()[0]

        ai_summary = "\n".join(notes)
        cur.execute("""
            INSERT INTO calls (lead_id, mission_name, transcript, ai_summary, call_date)
            VALUES (%s, %s, %s, %s, NOW())
        """, (lead_id, mission, transcript, ai_summary))
        
        conn.commit()
        cur.close()
        conn.close()
        return True, "Saved"
    except Exception as e:
        return False, str(e)
