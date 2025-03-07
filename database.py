from dotenv import load_dotenv
import sqlite3
import hashlib
import os
import json

# Load environment variables
load_dotenv()

# Initialize database
def init_db():
    conn = sqlite3.connect('app_data.db')
    c = conn.cursor()
    c.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        username TEXT UNIQUE,
        password TEXT
    )
    ''')
    c.execute('''
    CREATE TABLE IF NOT EXISTS batches (
        id INTEGER PRIMARY KEY,
        batch_id TEXT UNIQUE,
        status TEXT,
        messages TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    admin_username = os.getenv('ADMIN_USERNAME', 'admin')
    admin_password = os.getenv('ADMIN_PASSWORD', 'password')
    
    password_hash = hashlib.sha256(admin_password.encode()).hexdigest()
    
    c.execute("SELECT * FROM users WHERE username = ?", (admin_username,))
    if not c.fetchone():
        c.execute("INSERT INTO users (username, password) VALUES (?, ?)", 
                 (admin_username, password_hash))
    
    conn.commit()
    conn.close()

def verify_credentials(username, password):
    conn = sqlite3.connect('app_data.db')
    c = conn.cursor()
    
    password_hash = hashlib.sha256(password.encode()).hexdigest()
    
    c.execute("SELECT * FROM users WHERE username = ? AND password = ?", 
             (username, password_hash))
    user = c.fetchone()
    conn.close()
    
    return user is not None

def save_batch_to_db(batch_id, messages_json):
    conn = sqlite3.connect('app_data.db')
    c = conn.cursor()
    
    # First, ensure we have a batches table
    c.execute('''
    CREATE TABLE IF NOT EXISTS batches (
        id INTEGER PRIMARY KEY,
        batch_id TEXT UNIQUE,
        status TEXT,
        messages TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    c.execute("INSERT OR IGNORE INTO batches (batch_id, status, messages) VALUES (?, ?, ?)", 
             (batch_id, "processing", messages_json))
    
    conn.commit()
    conn.close()

def update_batch_status(batch_id, status):
    conn = sqlite3.connect('app_data.db')
    c = conn.cursor()
    
    c.execute("UPDATE batches SET status = ? WHERE batch_id = ?", 
             (status, batch_id))
    
    conn.commit()
    conn.close()
    
def get_batch_history():
    conn = sqlite3.connect('app_data.db')
    conn.row_factory = sqlite3.Row  # To get column names
    c = conn.cursor()
    
    c.execute("SELECT * FROM batches ORDER BY created_at DESC")
    batches = [dict(row) for row in c.fetchall()]
    
    conn.close()
    return batches

def get_batch_messages(batch_id):
    conn = sqlite3.connect('app_data.db')
    c = conn.cursor()
    
    c.execute("SELECT messages FROM batches WHERE batch_id = ?", (batch_id,))
    result = c.fetchone()
    
    conn.close()
    
    if result and result[0]:
        return json.loads(result[0])
    return None
