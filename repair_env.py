import os

# Your Config Data
DATA = {
    "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", ""),
    "DATABASE_URL": "postgresql://neondb_owner:npg_Iq0Nce5SAxET@ep-purple-sound-ae0z3iai-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require",
    "DEVICE_INDEX": "1",
    "MIC_NAME": "Voicemeeter"
}

# Write a clean file
with open(".env", "w", encoding="utf-8") as f:
    for key, value in DATA.items():
        if value:
            f.write(f"{key}={value}\n")

print("✅ .env file has been repaired and formatted correctly.")
