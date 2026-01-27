import os

# 1. The Key you provided
NEW_DB_URL = "postgresql://neondb_owner:npg_Iq0Nce5SAxET@ep-purple-sound-ae0z3iai-pooler.c-2.us-east-2.aws.neon.tech/neondb?sslmode=require&channel_binding=require"

# 2. Read existing file
lines = []
if os.path.exists(".env"):
    with open(".env", "r") as f:
        lines = f.readlines()

# 3. Clean and Update
new_lines = []
found_db = False

for line in lines:
    if line.strip().startswith("DATABASE_URL="):
        # Replace the old one
        new_lines.append(f"DATABASE_URL={NEW_DB_URL}\n")
        found_db = True
    else:
        new_lines.append(line)

# If we didn't find it, add it
if not found_db:
    if new_lines and not new_lines[-1].endswith('\n'):
        new_lines.append('\n')
    new_lines.append(f"DATABASE_URL={NEW_DB_URL}\n")

# 4. Save
with open(".env", "w") as f:
    f.writelines(new_lines)

print("✅ DATABASE KEY INJECTED SUCCESSFULLY.")
