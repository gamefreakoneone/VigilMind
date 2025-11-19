# VigilMind Desktop Monitoring - Setup & Testing Guide

## Prerequisites

### System Requirements
- **Windows 10/11** (for desktop monitoring)
- **Python 3.8+**
- **Node.js 16+** and npm
- **MongoDB** (local or MongoDB Atlas)

### Required Python Packages
```bash
pip install flask flask-cors pymongo openai psutil pillow pywin32 win10toast youtube-transcript-api agents pydantic
```

### Required Node Packages (for Parent Dashboard)
```bash
cd Parent_Dashboard
npm install
```

---

## Environment Setup

### 1. Set Environment Variables

Create a `.env` file in the `Big-Brother` directory:

```bash
# OpenAI API Key (required for AI agents)
OPENAI_API_KEY=your_openai_api_key_here

# MongoDB Connection
MONGO_URI=mongodb://localhost:27017/

# Email Configuration (for parent notifications)
PARENT_EMAIL=parent@example.com
EMAIL_PASSWORD=your_app_password

# Server Configuration
HOST=127.0.0.1
PORT=5000
```

### 2. Start MongoDB

**Local MongoDB:**
```bash
mongod --dbpath /path/to/data/directory
```

**Or use MongoDB Atlas** (cloud) and update `MONGO_URI` accordingly.

---

## Running the Application

### Step 1: Start the Backend Server

Open a terminal in the `Big-Brother` directory:

```bash
cd Big-Brother
python new_server.py
```

You should see:
```
MongoDB connection successful.
Initializing default monitoring configuration...
Monitoring configuration initialized.
Initializing critical system applications whitelist...
Protected 15 critical system applications
Starting email monitoring service...
Email monitoring service initialized.
Starting server on 127.0.0.1:5000...
```

**What this does:**
- Connects to MongoDB
- Initializes default monitoring configuration
- **Protects critical Windows apps** (explorer.exe, taskmgr.exe, etc.) by adding them to whitelist
- Starts Flask API server on port 5000
- Starts email monitoring for parent notifications

---

### Step 2: Start the Parent Dashboard

Open a **new terminal** in the `Parent_Dashboard` directory:

```bash
cd Parent_Dashboard
npm start
```

The dashboard will open at `http://localhost:3000`

**What this does:**
- Starts React development server
- Provides web interface for parents to:
  - Set monitoring guidelines
  - View blacklisted websites and apps
  - Approve/deny child appeals
  - Review desktop app screenshots

---

### Step 3: Start Desktop Monitoring

Open a **new terminal** (run as **Administrator** for best results):

```bash
cd Big-Brother/System_Monitoring
python active_window_test.py
```

You should see:
```
==================================================
PARENTAL DESKTOP MONITOR
==================================================
This will monitor all non-browser applications
Press Ctrl+C to stop
==================================================

✓ Connected to monitoring service

Desktop Monitor Started
==================================================
```

**What this does:**
- Monitors active desktop applications every 2 seconds
- Skips browsers (handled by browser extension)
- Skips whitelisted apps (Word, Excel, Calculator, etc.)
- Takes screenshots every 120 seconds for unknown apps
- Sends screenshots to AI for analysis
- Terminates apps if AI detects violations
- Shows Windows notifications when apps are blocked

---

## Testing Scenarios

### Test 1: Basic Monitoring

1. **Start all three components** (Backend, Dashboard, Desktop Monitor)
2. **Open the Parent Dashboard** (`http://localhost:3000`)
3. **Set monitoring guidelines:**
   - Parent Email: `your@email.com`
   - Monitoring Guidelines: `Block inappropriate content and attempts to bypass monitoring`
   - Save Configuration

**Expected Result:** Configuration saved successfully

---

### Test 2: Whitelisted Apps (No Screenshot)

1. **Open Microsoft Word, Excel, or Calculator**
2. **Check Desktop Monitor terminal**

**Expected Result:**
```
[HH:MM:SS] Active: WINWORD.EXE: Document1 - Word
```

No screenshot taken (app is whitelisted). Monitor continues silently.

---

### Test 3: Unknown App (Screenshot & Analysis)

1. **Open a non-whitelisted application** (e.g., Discord, Steam, custom game)
2. **Wait 120 seconds**
3. **Check Desktop Monitor terminal:**

**Expected Result:**
```
[HH:MM:SS] Active: discord.exe: Discord
📸 Taking screenshot of discord.exe...
```

**Two possible outcomes:**

**A) App Allowed:**
```
✓ discord.exe - Activity allowed
```

**B) App Blocked:**
```
⛔ Terminating discord.exe: This application may violate parental guidelines. Please wait for parental approval.
```

A Windows notification appears:
> "You might have violated the parental guidelines. Please wait for parental approval."

The app is terminated and added to the blacklist.

---

### Test 4: Blacklisted App (Immediate Termination)

If an app was previously blocked:

1. **Try to open the same app again**
2. **It will be terminated immediately** (no 120-second wait)

**Expected Result:**
```
[HH:MM:SS] Active: discord.exe: Discord
⚠ discord.exe is blacklisted - terminating
```

Windows notification appears and app closes.

---

### Test 5: Parent Review & Approval

1. **Go to Parent Dashboard** (`http://localhost:3000`)
2. **Scroll to "Blacklisted Desktop Applications" section**
3. **You should see:**
   - App name (e.g., `DISCORD.EXE`)
   - Timestamp when blocked
   - AI reasoning (why it was blocked)
   - **Screenshot preview** (click to enlarge)

4. **Click "✓ Approve & Unblock"**

**Expected Result:**
- App removed from blacklist
- Screenshot deleted from server
- Child can now use the app freely

---

### Test 6: Prompt Change (Clear AI Lists)

This tests the new feature where changing guidelines clears old AI decisions.

1. **Go to Parent Dashboard**
2. **Change Monitoring Guidelines** to something different:
   - Old: `Block inappropriate content`
   - New: `Allow everything except violent games`
3. **Click Save Configuration**

**Expected Result in Backend Terminal:**
```
Monitoring prompt changed - clearing AI-generated lists...
Removed X AI-generated blacklist entries
Removed X AI-generated whitelist entries
Removed X AI-generated desktop blacklist entries
Initializing critical system applications whitelist...
Protected 15 critical system applications
```

**What happens:**
- All AI-generated web blacklists/whitelists are cleared
- All AI-generated desktop blacklists are cleared
- **Manually-added entries are preserved**
- Critical system apps are re-protected

The AI will now make fresh decisions based on the new guidelines.

---

### Test 7: Critical System Apps (Protected)

This tests that critical Windows apps can never be blocked.

1. **Try to trigger analysis on File Explorer** (open many folders, browse files)
2. **Check Desktop Monitor output:**

**Expected Result:**
```
[HH:MM:SS] Active: explorer.exe: C:\Users\...
```

No screenshot taken, no analysis. `explorer.exe` is protected and can never be terminated.

**Other protected apps:**
- `taskmgr.exe` (Task Manager)
- `chrome.exe`, `firefox.exe`, `msedge.exe` (Browsers)
- `dwm.exe` (Desktop Window Manager)
- `services.exe`, `svchost.exe`, `lsass.exe` (System services)

---

## Understanding the Win32 API Error

### The Error Message:
```
WNDPROC return value cannot be converted to LRESULT
TypeError: WPARAM is simple, so must be an int object (got NoneType)
```

### What It Means:
This error occurs when Windows is processing window messages but the Win32 API receives `None` instead of an integer. This typically happens when:

1. **A window is being destroyed** while we're trying to access it
2. **System-protected windows** that don't allow external access
3. **Permission issues** accessing certain processes

### The Fix:
The updated code now:
- **Validates `hwnd`** before accessing it
- **Wraps all Win32 calls** in try-except blocks
- **Silently ignores** common API errors instead of logging spam
- **Returns `None`** gracefully when window access fails

**Result:** No more error messages, monitoring continues smoothly.

---

## Troubleshooting

### Backend Server Won't Start

**Error:** `ERROR: Could not connect to MongoDB`

**Solution:**
- Ensure MongoDB is running: `mongod`
- Check `MONGO_URI` in your environment variables
- Try: `MONGO_URI=mongodb://localhost:27017/`

---

### Desktop Monitor Can't Terminate Apps

**Error:** `Error terminating process: [WinError 5] Access is denied`

**Solution:**
- **Run as Administrator:** Right-click terminal → "Run as Administrator"
- Some apps require admin privileges to terminate

---

### Screenshots Not Saving

**Error:** `Error saving screenshot: [Errno 13] Permission denied`

**Solution:**
- Check that `Big-Brother/screenshots/` directory exists
- Ensure write permissions: `mkdir screenshots` in Big-Brother folder

---

### Parent Dashboard Won't Connect

**Error:** Dashboard shows "Error loading dashboard data"

**Solution:**
- Ensure backend server is running on port 5000
- Check `API_BASE` in `Parent_Dashboard/src/App.js` is set to `http://127.0.0.1:5000`
- Check browser console for CORS errors

---

### OpenAI API Errors

**Error:** `ERROR during desktop screenshot analysis: 401 Unauthorized`

**Solution:**
- Check `OPENAI_API_KEY` environment variable is set correctly
- Ensure you have API credits
- Verify key has access to `gpt-4.1-mini` model

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────┐
│                   Parent Dashboard                       │
│              (React App - Port 3000)                     │
│  • View blacklisted apps                                 │
│  • Review screenshots                                    │
│  • Approve/deny appeals                                  │
└──────────────────────┬──────────────────────────────────┘
                       │ HTTP Requests
                       ▼
┌─────────────────────────────────────────────────────────┐
│               Flask Backend Server                       │
│                  (Port 5000)                             │
│  • Web content analysis (browser extension)              │
│  • Desktop screenshot analysis (vision AI)               │
│  • MongoDB management                                    │
│  • Email notifications                                   │
└──────────────────────┬──────────────────────────────────┘
                       │
        ┌──────────────┴──────────────┐
        ▼                             ▼
┌───────────────────┐      ┌────────────────────────┐
│    MongoDB        │      │  Desktop Monitor       │
│  • whitelist      │      │  (active_window_test)  │
│  • blacklist      │      │  • Track active apps   │
│  • desktop_apps   │      │  • Take screenshots    │
│  • config         │      │  • Terminate violators │
└───────────────────┘      └────────────────────────┘
```

---

## Key Features Implemented

✅ **Critical System Protection** - 15 essential Windows apps protected from termination
✅ **Smart Whitelisting** - Common productivity apps skip screenshots
✅ **Vision AI Analysis** - GPT-4.1-mini analyzes desktop screenshots
✅ **Automatic Termination** - Violating apps closed immediately
✅ **Windows Notifications** - Toast alerts when apps are blocked
✅ **Parent Dashboard** - Web interface for review and approval
✅ **Prompt-Based Clearing** - AI lists cleared when guidelines change
✅ **Error Handling** - Win32 API errors handled gracefully
✅ **Screenshot Storage** - Images saved for parental review
✅ **Real-time Monitoring** - 2-second window checks, 120-second screenshots

---

## Next Steps

1. **Install browser extension** (for web monitoring)
2. **Configure email notifications** (for parent alerts)
3. **Set up auto-start** (run monitoring on system startup)
4. **Customize whitelist** (add your preferred safe apps)

---

**Note:** This is a powerful parental control system. Always test in a controlled environment before deploying for actual child monitoring. Ensure compliance with local privacy laws and family agreements.
