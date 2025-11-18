# VigilMind - AI-Powered Parental Control System

## Project Vision

VigilMind is an intelligent, AI-driven parental control system that monitors children's digital activity across web browsers and desktop applications. Unlike traditional blocklist-based solutions, VigilMind uses advanced AI agents powered by OpenAI's SDK to make contextual, guideline-based decisions about content appropriateness.

The system empowers parents to set natural language guidelines and choose their level of involvement, while giving children the ability to appeal decisions through an AI-mediated process.

---

## Core Philosophy

1. **Natural Language Configuration**: Parents define monitoring rules in plain English, not rigid rule sets
2. **Context-Aware AI Decisions**: AI agents analyze content based on guidelines, not just URL patterns
3. **Child Agency with Oversight**: Children can appeal blocks, fostering communication and trust
4. **Flexible Automation**: Parents choose whether AI auto-approves appeals or requires manual review
5. **Multi-Channel Monitoring**: Covers both web browsing and desktop applications to prevent circumvention

---

## System Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────────┐
│                        VigilMind System                      │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  ┌──────────────┐    ┌──────────────┐    ┌──────────────┐ │
│  │   Browser    │    │   Desktop    │    │   Parent     │ │
│  │  Extension   │    │   Worker     │    │  Dashboard   │ │
│  │  (browser-   │    │ (System_Mon- │    │  (MISSING)   │ │
│  │   eyes/)     │    │  itoring/)   │    │              │ │
│  └──────┬───────┘    └──────┬───────┘    └──────┬───────┘ │
│         │                   │                    │          │
│         └───────────────┬───┴────────────────────┘          │
│                         │                                   │
│                  ┌──────▼──────┐                           │
│                  │  Flask API  │                           │
│                  │   Server    │                           │
│                  │(new_server) │                           │
│                  └──────┬──────┘                           │
│                         │                                   │
│         ┌───────────────┼───────────────┐                  │
│         │               │               │                  │
│    ┌────▼────┐    ┌────▼────┐    ┌────▼────┐             │
│    │   AI    │    │  Email  │    │ MongoDB │             │
│    │ Agents  │    │  Agent  │    │Database │             │
│    │ (OpenAI)│    │ (Gmail) │    │         │             │
│    └─────────┘    └─────────┘    └─────────┘             │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

---

## Component Breakdown

### 1. Browser Extension (`browser-eyes/`)

**Status**: ✅ Core Features Working, ⚠️ Critical Bugs Exist
**Platform**: Chrome/Edge (Manifest V3)
**Technology**: JavaScript, Webpack, @mozilla/readability

**Responsibilities**:
- Intercept all page loads with loading overlay
- Extract readable content from web pages using Mozilla Readability
- Send content to server for AI analysis
- Display block screen with appeal option for inappropriate content
- Handle child appeals and communicate with server
- Maintain seamless UX with visual feedback

**Key Files**:
- `src/content-script.js`: Main content monitoring and UI logic (361 lines)
- `src/background.js`: Extension background service (minimal, 6 lines)
- `manifest.json`: Extension configuration and permissions
- `webpack.config.js`: Build configuration

**Current Working Features**:
- ✅ Content extraction from web pages
- ✅ Beautiful loading overlay with spinner
- ✅ Block page UI with glassmorphism design
- ✅ Cache checking (whitelist/blacklist before AI analysis)
- ✅ POST requests to `/analyze` and `/appeal` endpoints

**Critical Issues**:
- 🐛 **Appeal submission broken** - Syntax error on line 258: `statusDiv.textContent = + data.message;` should be `= data.message;`
- 🐛 **Appeal counter check incomplete** - Line 91 doesn't verify if appeals have been used up
- 🐛 **No dynamic content blocking** - Extension only analyzes on page load, not when content changes (e.g., YouTube search results load via AJAX). If YouTube is allowed but WW2 videos should be blocked, content loads without re-analysis
- ⚠️ **Hardcoded server URL** - localhost:5000 not suitable for production
- ⚠️ **No settings UI** within extension
- ⚠️ **UI redesign needed** - Current purple emoji-filled design needs refinement (lower priority)

**Required Fixes**:
1. Fix appeal submission syntax error
2. Implement dynamic content monitoring (MutationObserver for SPAs)
3. Add appeal counter validation before showing appeal option
4. Configuration endpoint for server URL

---

### 2. Desktop Worker (`Big-Brother/System_Monitoring/`)

**Status**: ✅ Client Implemented, ❌ Server Integration Missing
**Platform**: Windows
**Technology**: Python, win32gui, psutil, PIL

**Responsibilities**:
- Monitor active window and running processes
- Filter out browser processes (already monitored by extension)
- Capture screenshots when new applications open
- Periodic screenshot capture (configurable interval, default 120s)
- Send screenshots to server for AI analysis
- Terminate applications deemed inappropriate

**Key Files**:
- `active_window_test.py`: Complete desktop monitoring implementation (200 lines)
- `screenshot.py`: Empty (functionality in active_window_test.py)

**Current Working Features**:
- ✅ Active window detection
- ✅ Screenshot capture (base64 PNG)
- ✅ Browser process filtering (Chrome, Firefox, Edge, Brave)
- ✅ Process termination capability
- ✅ Configuration fetching

**Missing Implementation**:
- ❌ **Server endpoint** `/desktop/screenshot` doesn't exist
- ❌ **AI vision agent** for screenshot analysis
- ❌ **Local screenshot storage** for privacy audit trail (required before sending to OpenAI)
- ❌ **Desktop agent file** (`desktop_agent.py` is empty)
- ⚠️ **Platform limitation** - Windows-only (uses win32gui)

**Integration Needed**:
1. Server endpoint: `POST /desktop/screenshot`
2. AI agent with vision capabilities for desktop content analysis
3. Local screenshot storage system (save before sending to AI)
4. App termination logic implementation
5. Configuration sync with parent settings

---

### 3. Flask API Server (`Big-Brother/new_server.py`)

**Status**: ✅ Core Functionality Complete, ⚠️ Integrations Missing
**Technology**: Flask, MongoDB, OpenAI API, YouTube Transcript API
**Lines of Code**: 635

**Current Endpoints**:

| Endpoint | Method | Purpose | Status |
|----------|--------|---------|--------|
| `/analyze` | POST | Analyze web page content | ✅ Working |
| `/appeal` | POST | Handle child appeal requests | ✅ Working |
| `/whitelist` | GET | Retrieve whitelisted domains | ✅ Working |
| `/blacklist` | GET | Retrieve blacklisted domains | ✅ Working |
| `/initialize` | POST | Set parental configuration | ✅ Working |
| `/desktop/screenshot` | POST | Desktop content analysis | ❌ Missing |
| `/config` | GET | Get current configuration | ❌ Missing |

**AI Agents**:

1. **web_checker_agent** (Lines 279-285):
   - Model: GPT-5-mini (fast, cost-effective)
   - Analyzes web content against parental guidelines
   - Tools: WebSearchTool, get_youtube_transcript()
   - Returns structured decision (allow/block + reason)

2. **appeal_agent** (Lines 440-445):
   - Model: GPT-4.1 (smarter, more nuanced)
   - Evaluates child appeal requests
   - Considers: child's reasoning, parental guidelines, page content, previous decisions
   - Auto-approves if agent_can_auto_approve = true
   - Returns structured decision (approve/deny/escalate)

**Database Schema** (MongoDB - NorthlightDB):

```javascript
// whitelist collection
{
  link: "https://example.com",
  added_at: ISODate("2025-11-17T..."),
  reason: "Educational website approved by AI"
}

// blacklist collection
{
  link: "https://blocked.com",
  appeals: 0,  // Number of appeals made (max 1)
  last_appeal_message: "I need this for homework",
  added_at: ISODate("..."),
  reason: "Contains inappropriate content"
}

// appeals collection
{
  appeal_id: "appeal_1234567890",
  link: "https://example.com/page",
  domain: "example.com",
  child_reason: "I need this for homework",
  timestamp: ISODate("..."),
  status: "approved" | "denied" | "pending"
}

// pending_approvals collection
{
  approval_id: "approval_1234567890",
  appeal_id: "appeal_1234567890",
  link: "https://example.com/page",
  domain: "example.com",
  child_reason: "I need this for homework",
  timestamp: ISODate("..."),
  status: "pending" | "approved" | "denied"
}

// config collection
{
  type: "web" | "desktop",
  parent_email: "parent@example.com",
  monitoring_prompt: "Block any content with violence or adult themes...",
  agent_can_auto_approve: true | false,
  desktop_monitoring_enabled: true | false,
  screenshot_interval: 120,  // seconds
  blocked_apps: ["game.exe", "chat.exe"]
}

// desktop_events collection (planned, not yet used)
{
  event_id: "desktop_1234567890",
  window_title: "Game - Level 5",
  process_name: "game.exe",
  screenshot_path: "/screenshots/2025-11-17_10-30-00.png",
  timestamp: ISODate("..."),
  ai_decision: "block" | "allow",
  reason: "Gaming during school hours"
}
```

**Current Limitations**:
- No authentication/authorization on endpoints
- Runs on localhost only (127.0.0.1:5000)
- No HTTPS support
- No rate limiting
- No API documentation (OpenAPI/Swagger)
- Appeal limit (1 per URL) has no frontend feedback

---

### 4. Email Agent (`Big-Brother/Agent_Tools/Email/gmail_agent.py`)

**Status**: ✅ Fully Implemented, ❌ NOT Integrated
**Technology**: Google Gmail API, OAuth2
**Lines of Code**: 389

**Capabilities**:
- OAuth2 authentication with Google
- Send emails (HTML support, CC/BCC, attachments)
- Receive and parse emails
- Monitor inbox for new messages
- Reply to email threads
- Mark messages as read

**Integration Points** (Currently Stubs in `email_agent.py`):
- `notify_parent_appeal_approved()`: Send notification when AI auto-approves (Line 542)
- `send_approval_request_email()`: Send appeal to parent for manual review (Line 563)

Both functions are called by the server but contain only `pass` statements.

**Configuration Required**:
- Google Cloud Console project
- Gmail API enabled
- OAuth2 credentials (`credentials.json`)
- Token storage (`token.pickle`)

**Missing Implementation**:
- Email templates (HTML/text)
- Parent response parsing logic
- Integration with main server appeal flow
- Notification triggers

---

### 5. Parent Dashboard

**Status**: ❌ Does NOT Exist
**Technology**: Next.js + Tailwind CSS (planned)

**Required Features**:

**Configuration Page**:
- Set monitoring guidelines (natural language textarea)
- Configure parent email for notifications
- Toggle: Allow AI to auto-approve appeals
- Toggle: Enable desktop monitoring
- Toggle: Auto-populate blocklist with known adult sites
- Set screenshot interval
- Manage blocked applications list

**Monitoring Dashboard**:
- Real-time activity feed (websites visited, blocks, appeals)
- Statistics: Total blocks, appeals, auto-approvals today/week/month
- Recent screenshots from desktop worker
- Active sessions indicator

**Appeals Management**:
- List of pending appeals requiring parent review
- For each appeal:
  - Show: website/app, child's reason, AI analysis, screenshot/content preview
  - Actions: Approve, Deny, Add to whitelist permanently
- Appeal history with filters (approved/denied, date range)

**Whitelisting Management**:
- Manual domain whitelist (add/remove)
- View AI-approved links (with revoke option)
- Blacklist management

**API Integration Needed**:
- `GET /config`: Fetch current configuration
- `POST /config`: Update configuration
- `GET /activity`: Fetch recent activity logs
- `GET /appeals/pending`: Get pending appeals
- `POST /appeals/approve`: Approve/deny appeals
- `GET /stats`: Get usage statistics

**Notes**:
- No analytics charts initially (no Chart.js needed yet)
- Focus on functional MVP first, polish later
- Desktop notifications when parent approves appeal

---

### 6. Static Blocklists (`Blocklists/`)

**Status**: ⚠️ Data Exists, Planned for Overhaul
**Contents**:
- `blocklists.json`: Categorized blocklist (adult, gambling, malware, etc.)
- `oisd_nsfw_domainswild2.txt`: Large NSFW domain list
- `blocklist_manager.py`: Empty

**Current Usage**: Not actively used by server (AI makes dynamic decisions)

**Planned Implementation**:
- Dashboard toggle: "Enable adult content blocklist"
- When toggled ON: Auto-populate MongoDB blacklist collection with domains from files
- When toggled OFF: Remove auto-populated entries from database
- Parent can still manually add/remove specific domains
- Faster response for known bad domains (skip AI analysis)
- Reduce OpenAI API costs

**Benefits**:
- Optional safety net for conservative parents
- Pre-filter obvious adult/malware domains
- Immediate blocking without AI latency
- Cost optimization

---

## User Workflows

### Workflow 1: Initial Setup (Parent)

1. Parent installs browser extension on child's Chrome/Edge
2. Parent installs desktop worker (background process)
3. Parent accesses dashboard (when built) or runs `/initialize` API call
4. Parent sets monitoring guidelines in natural language:
   ```
   "Block any content containing violence, adult themes, or inappropriate
   language. Allow educational content about science and history. Gaming
   is allowed for 1 hour on weekends only."
   ```
5. Parent adds trusted domains to whitelist (e.g., school websites)
6. Parent sets email address for notifications
7. Parent chooses: "AI can auto-approve appeals" (yes/no)
8. Parent toggles: "Enable adult content blocklist" (optional)
9. System saves configuration to MongoDB
10. Monitoring begins immediately

---

### Workflow 2: Web Browsing (Child)

**Current Implementation**:

```
┌─────────────────────────────────────────────────────────────┐
│  Child navigates to website                                  │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────┐
│  Extension shows loading overlay: "Checking content..."      │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────┐
│  Extract page content (text, images, videos)                 │
│  Uses @mozilla/readability library                           │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────┐
│  Send to server: POST /analyze                               │
│  { url, content, screenshots }                               │
└─────────────────┬───────────────────────────────────────────┘
                  │
          ┌───────┴───────┐
          │               │
┌─────────▼─────┐   ┌─────▼──────────┐
│ Check cache:  │   │ Not in cache:  │
│ - Whitelist   │   │ Call AI agent  │
│ - Blacklist   │   │ to analyze     │
└─────────┬─────┘   └─────┬──────────┘
          │               │
          └───────┬───────┘
                  │
          ┌───────┴───────┐
          │               │
┌─────────▼─────┐   ┌─────▼──────────┐
│  ALLOWED      │   │  BLOCKED       │
│  - Hide       │   │  - Show block  │
│    overlay    │   │    screen      │
│  - Show page  │   │  - Add to      │
│               │   │    blacklist   │
└───────────────┘   └─────┬──────────┘
                          │
                  ┌───────▼────────┐
                  │ Child clicks   │
                  │ "Appeal" btn   │
                  └───────┬────────┘
                          │
                  ┌───────▼────────────────────┐
                  │ Child enters reason:       │
                  │ "I need this for homework" │
                  └───────┬────────────────────┘
                          │
                  ┌───────▼────────┐
                  │ POST /appeal   │
                  │ (Max 1 per URL)│
                  └───────┬────────┘
                          │
                  ┌───────┴───────┐
                  │               │
        ┌─────────▼─────┐   ┌─────▼──────────────┐
        │ AI evaluates  │   │ agent_can_auto_    │
        │ appeal        │   │ approve = false    │
        │               │   │                    │
        │ Decision:     │   │ Send email to      │
        │ APPROVE       │   │ parent (STUB)      │
        └─────────┬─────┘   │                    │
                  │         │ Add to pending_    │
        ┌─────────▼─────┐   │ approvals          │
        │ Add to        │   └─────┬──────────────┘
        │ whitelist     │         │
        │               │   ┌─────▼──────────────┐
        │ Page auto-    │   │ Parent reviews in  │
        │ reloads       │   │ dashboard or email │
        │ (reload:true) │   │ (FUTURE)           │
        └───────────────┘   └────────────────────┘
```

**Known Issues**:
- Appeal submission has syntax bug (not functional)
- Dynamic content (AJAX/SPA navigation) not re-analyzed
- No feedback if appeal quota (1) already used

---

### Workflow 3: Desktop Monitoring (Child)

**Planned Implementation** (Not fully connected):

```
┌─────────────────────────────────────────────────────────────┐
│  Desktop Worker runs in background (every 120 seconds)       │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────┐
│  Detect active window change OR interval elapsed             │
│  - Window title: "Discord - #general"                        │
│  - Process: Discord.exe                                      │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────┐
│  Filter: Is it a browser? (Chrome, Firefox, Edge, Brave)     │
│  - YES: Skip (already monitored by extension)                │
│  - NO: Continue to screenshot                                │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────┐
│  Capture screenshot of active window                         │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────┐
│  Save screenshot locally (privacy audit trail)               │
│  /screenshots/YYYY-MM-DD_HH-MM-SS.png                        │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────┐
│  Send to server: POST /desktop/screenshot (MISSING!)         │
│  {                                                           │
│    window_title: "Discord - #general",                       │
│    process_name: "Discord.exe",                              │
│    screenshot_base64: "data:image/png;base64,...",           │
│    screenshot_path: "/screenshots/2025-11-17_10-30-00.png",  │
│    timestamp: "2025-11-17T10:30:00Z"                         │
│  }                                                           │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────┐
│  Server checks config:                                       │
│  - Is Discord.exe in blocked_apps? → Terminate immediately   │
│  - Is desktop_monitoring_enabled? → Continue                 │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────┐
│  AI Agent analyzes screenshot + window title                 │
│  - Uses vision model (GPT-4.1 with vision)                   │
│  - Compares against parental guidelines                      │
│  - Checks for inappropriate content, time restrictions       │
└─────────────────┬───────────────────────────────────────────┘
                  │
          ┌───────┴───────┐
          │               │
┌─────────▼─────┐   ┌─────▼──────────┐
│  ALLOWED      │   │  BLOCKED       │
│  - Continue   │   │  - Terminate   │
│    monitoring │   │    process     │
│  - Next check │   │  - Desktop     │
│    in 120s    │   │    notification│
│               │   │  - Email parent│
└───────────────┘   └────────────────┘
```

**Implementation Gaps**:
1. Server endpoint `/desktop/screenshot` doesn't exist
2. No vision-based AI agent for screenshot analysis
3. No local screenshot storage implementation
4. No process termination mechanism
5. No desktop-specific appeal system
6. No desktop notification system

---

### Workflow 4: Parent Email Approval

**Desired Flow** (Not implemented):

```
┌─────────────────────────────────────────────────────────────┐
│  Child appeal escalated to parent (agent_can_auto_approve   │
│  = false OR AI uncertain)                                    │
└─────────────────┬───────────────────────────────────────────┘
                  │
┌─────────────────▼───────────────────────────────────────────┐
│  Email Agent sends notification to parent:                   │
│                                                              │
│  Subject: [VigilMind] Appeal Request from Child              │
│                                                              │
│  Body:                                                       │
│  Your child has appealed a blocked website:                  │
│                                                              │
│  Website: https://example.com/game                           │
│  Blocked Reason: Contains gaming content during school       │
│  Child's Reason: "This is an educational math game for       │
│                   my homework assignment"                    │
│                                                              │
│  [Approve] [Deny]                                            │
│                                                              │
│  Or reply with "APPROVE" or "DENY" to this email.            │
│                                                              │
│  View details: https://vigilmind.app/appeals/12345           │
└─────────────────┬───────────────────────────────────────────┘
                  │
          ┌───────┴───────┐
          │               │
┌─────────▼─────┐   ┌─────▼──────────┐
│ Parent clicks │   │ Parent replies │
│ [Approve]     │   │ to email with  │
│ button in     │   │ "APPROVE"      │
│ email         │   │                │
│               │   │ Email agent    │
│ → Redirects   │   │ monitors inbox │
│ to dashboard  │   │ every 60s      │
└─────────┬─────┘   └─────┬──────────┘
          │               │
          └───────┬───────┘
                  │
┌─────────────────▼───────────────────────────────────────────┐
│  Server receives approval:                                   │
│  - Update pending_approvals: status = "approved"             │
│  - Add domain to whitelist                                   │
│  - Remove from blacklist                                     │
│  - Send confirmation email to parent                         │
│  - Send desktop notification to child (approved!)            │
└─────────────────────────────────────────────────────────────┘
```

**Implementation Status**:
- Gmail agent: ✅ Complete (389 lines)
- Email templates: ❌ Missing
- Send appeal email: ❌ Stub only (`pass` statement)
- Monitor inbox: ❌ Not implemented
- Parse parent response: ❌ Not implemented
- Dashboard approval UI: ❌ Dashboard doesn't exist
- Desktop notification: ❌ Not implemented

---

## Technical Stack

### Backend

| Technology | Purpose | Status |
|------------|---------|--------|
| **Python 3.x** | Primary language | ✅ |
| **Flask** | Web framework | ✅ |
| **MongoDB** | Database (PyMongo) | ✅ |
| **OpenAI API** | LLM for content analysis | ✅ |
| **OpenAI Agents SDK** | Structured AI agents | ✅ |
| **Google Gmail API** | Email notifications | ⚠️ Ready, not integrated |
| **youtube-transcript-api** | Video content analysis | ✅ |
| **win32gui** | Windows API (desktop monitoring) | ⚠️ Ready, not integrated |
| **psutil** | Process management | ⚠️ Ready, not integrated |
| **PIL (Pillow)** | Screenshot capture | ⚠️ Ready, not integrated |

### Frontend (Browser Extension)

| Technology | Purpose | Status |
|------------|---------|--------|
| **JavaScript** | Extension logic | ✅ |
| **Webpack 5** | Build tool | ✅ |
| **@mozilla/readability** | Content extraction | ✅ |
| **Chrome Extension Manifest V3** | Extension framework | ✅ |

### Frontend (Dashboard) - MISSING

| Technology | Purpose | Status |
|------------|---------|--------|
| **Next.js** | React framework | ❌ Not started |
| **Tailwind CSS** | Styling | ❌ Not started |
| **React** | UI framework | ❌ Not started |

### Infrastructure

| Component | Current State | Production Needs |
|-----------|---------------|------------------|
| **Server Hosting** | Localhost (127.0.0.1:5000) | VPS/Cloud (AWS, DigitalOcean) |
| **Database** | Local MongoDB | MongoDB Atlas (cloud) |
| **HTTPS** | None | Let's Encrypt SSL |
| **Authentication** | None | JWT or OAuth2 |
| **Logging** | Print statements | Structured logging |
| **Monitoring** | None | Sentry, DataDog, or similar |

---

## Configuration & Environment

### Environment Variables

Required in `.env` file (not committed to git):

```bash
# OpenAI Configuration
OPENAI_API_KEY=sk-proj-...
OPENAI_MODEL_ANALYZER=gpt-5-mini  # Fast model for content analysis
OPENAI_MODEL_APPEALS=gpt-4.1      # Smarter model for appeals

# MongoDB Configuration
MONGO_URI=mongodb://localhost:27017/
# Or for MongoDB Atlas:
# MONGO_URI=mongodb+srv://user:pass@cluster.mongodb.net/NorthlightDB

# Flask Server Configuration
HOST=127.0.0.1  # Change to 0.0.0.0 for network access
PORT=5000
FLASK_ENV=development  # or production

# Gmail API (for email notifications)
GMAIL_CREDENTIALS_PATH=credentials.json
GMAIL_TOKEN_PATH=token.pickle

# Monitoring Configuration (optional, can be set in dashboard)
DEFAULT_SCREENSHOT_INTERVAL=120  # seconds
DEFAULT_MONITORING_PROMPT="Block inappropriate content for a 12-year-old"
```

### File Structure

```
VigilMind/
├── .env                          # ❌ Not committed (create from .env.example)
├── .env.example                  # ⚠️  Should create
├── .gitignore                    # ✅ Exists
├── claude.md                     # ✅ This file
├── README.md                     # ⚠️  Should create (user-facing docs)
│
├── Big-Brother/                  # Backend server
│   ├── new_server.py             # ✅ Main Flask server (635 lines)
│   ├── server(deprecated).py     # ❌ Old version (can delete)
│   ├── prompts.py                # ✅ LLM prompt templates (50 lines)
│   ├── email_agent.py            # ⚠️  Stubs (6 lines, needs implementation)
│   ├── desktop_agent.py          # ❌ Empty
│   ├── appeal_agent.py           # ⚠️  Minimal (logic in new_server.py)
│   ├── setup.py                  # ✅ Testing utilities
│   ├── requirements.txt          # ⚠️  Should create
│   │
│   ├── Agent_Tools/              # Modular agent tools
│   │   ├── Email/
│   │   │   ├── gmail_agent.py    # ✅ Complete Gmail integration (389 lines)
│   │   │   ├── credentials.json  # ❌ Not committed (OAuth2 creds)
│   │   │   └── token.pickle      # ❌ Not committed (OAuth2 token)
│   │   └── Time_management/
│   │       └── time.py           # ⚠️  Stub only
│   │
│   └── System_Monitoring/        # Desktop monitoring
│       ├── active_window_test.py # ✅ Complete desktop monitor (200 lines)
│       └── screenshot.py         # ❌ Empty
│
├── browser-eyes/                 # Browser extension
│   ├── package.json              # ✅ NPM configuration
│   ├── webpack.config.js         # ✅ Build configuration
│   ├── dist/                     # Build output (git ignored)
│   ├── src/
│   │   ├── content-script.js     # ✅ Main extension logic (361 lines, has bugs)
│   │   └── background.js         # ⚠️  Minimal implementation (6 lines)
│   └── manifest.json             # ✅ Extension manifest
│
├── Blocklists/                   # Static blocklists
│   ├── blocklists.json           # ✅ Categorized blocklist
│   ├── oisd_nsfw_domainswild2.txt # ✅ NSFW domains
│   └── blocklist_manager.py      # ❌ Empty (planned: DB population)
│
├── dashboard/                    # ❌ Parent dashboard (doesn't exist)
│   └── (Future Next.js implementation)
│
├── screenshots/                  # ⚠️  Should create (local screenshot storage)
│
├── test.py                       # Development/testing file
├── website_monitor.py            # Hosts file manipulation utility
└── playgrounds.ipynb             # Development notebook
```

---

## Development Priorities

### ✅ Phase 1: Fix Critical Bugs (IMMEDIATE)

**Goal**: Make existing features actually work

1. **Browser Extension Fixes**:
   - Fix appeal submission syntax error (line 258)
   - Fix appeal counter validation (line 91)
   - Test appeal workflow end-to-end

2. **Desktop Monitoring Integration**:
   - Create `/desktop/screenshot` endpoint
   - Implement screenshot local storage
   - Create vision-based AI agent for screenshot analysis
   - Test full desktop workflow

3. **Email Integration**:
   - Connect gmail_agent.py to email_agent.py
   - Implement notification functions
   - Create email templates (HTML)
   - Test parent email notification flow

### 🎯 Phase 2: Parent Dashboard MVP (HIGH PRIORITY)

**Goal**: Give parents control without API calls

**Technology**: Next.js + Tailwind CSS

**Features**:
1. **Configuration Page**:
   - Set monitoring guidelines (textarea)
   - Set parent email
   - Toggle: AI auto-approve appeals
   - Toggle: Desktop monitoring enabled
   - Toggle: Auto-populate adult blocklist
   - Set screenshot interval
   - Manage blocked apps list

2. **Pending Appeals Page**:
   - List pending appeals
   - Show: URL, child's reason, AI analysis
   - Actions: Approve, Deny
   - Desktop notification on approval

3. **Activity Log**:
   - Last 50 events (blocks, appeals, approvals)
   - Filter by date/type

**API Endpoints Needed**:
- `GET /config`
- `POST /config`
- `GET /appeals/pending`
- `POST /appeals/{id}/approve`
- `POST /appeals/{id}/deny`
- `GET /activity`

### 🚀 Phase 3: Advanced Features (FUTURE)

**Deferred until MVP working**:
- Security hardening (authentication, HTTPS, rate limiting)
- Time management features
- Analytics and reporting
- Multi-child profiles
- Mobile support
- Production deployment

---

## Current Status Summary

### ✅ What's Actually Working

1. **Web Content Analysis**:
   - AI analyzes page content against parental guidelines
   - YouTube transcript extraction
   - Whitelist/blacklist caching
   - Loading overlay display

2. **Database Architecture**:
   - MongoDB schema well-designed
   - Proper indexing
   - All collections created

3. **Desktop Monitoring Client**:
   - Window tracking
   - Screenshot capture
   - Browser filtering
   - Process detection

4. **Gmail Integration Code**:
   - Full OAuth2 implementation
   - Send/receive capabilities
   - Thread management

### 🐛 What's Broken

1. **Appeal submission** - Syntax error prevents appeals from working
2. **Dynamic content blocking** - SPA navigation not monitored
3. **Email notifications** - Functions are stubs
4. **Desktop server integration** - Endpoint missing

### ❌ What's Missing

1. **Parent dashboard** - No UI at all
2. **Desktop screenshot endpoint** - Server doesn't receive screenshots
3. **Vision AI agent** - No desktop content analysis
4. **Desktop notifications** - No notification system
5. **Local screenshot storage** - Privacy audit trail
6. **Blocklist auto-population** - Toggle feature not built

---

## AI Models Used

**Important**: The codebase uses the following OpenAI models:

1. **GPT-5-mini** - Fast, cost-effective model for web content analysis
2. **GPT-4.1** - Smarter model for nuanced appeal evaluation and vision analysis

These are referenced in the code and should NOT be renamed or changed without consulting the latest OpenAI documentation.

---

## Common Development Tasks

### Running the System Locally

**1. Start MongoDB**:
```bash
# If using local MongoDB
mongod --dbpath /path/to/data

# If using MongoDB Atlas
# Just set MONGO_URI in .env
```

**2. Start Flask Server**:
```bash
cd Big-Brother/
python new_server.py
# Server runs on http://127.0.0.1:5000
```

**3. Build Browser Extension**:
```bash
cd browser-eyes/
npm install
npm run build
# Load unpacked extension from browser-eyes/dist/ in Chrome
```

**4. Run Desktop Worker** (once integrated):
```bash
cd Big-Brother/System_Monitoring/
python active_window_test.py
```

### Testing Workflows

**Test Browser Blocking**:
```python
import requests

response = requests.post('http://localhost:5000/analyze', json={
    'url': 'https://example.com',
    'content': 'This is a test page about educational science topics.',
    'title': 'Science Education'
})
print(response.json())
# Expected: {'action': 'allow', 'reason': '...'}
```

**Test Appeal**:
```python
response = requests.post('http://localhost:5000/appeal', json={
    'url': 'https://example.com/blocked-page',
    'child_reason': 'I need this for my homework assignment',
    'page_content': 'Content of the blocked page...'
})
print(response.json())
```

**Test Configuration**:
```python
response = requests.post('http://localhost:5000/initialize', json={
    'parent_email': 'parent@example.com',
    'monitoring_prompt': 'Block violent and adult content for a 12-year-old',
    'agent_can_auto_approve': True,
    'desktop_monitoring_enabled': True,
    'screenshot_interval': 120,
    'blocked_apps': ['game.exe']
})
print(response.json())
```

### Database Queries

```python
from pymongo import MongoClient

client = MongoClient('mongodb://localhost:27017/')
db = client['NorthlightDB']

# Get all pending appeals
pending = db.pending_approvals.find({'status': 'pending'})

# Get config
config = db.config.find_one({'type': 'web'})

# Get today's blocks
from datetime import datetime, timedelta
today = datetime.now().replace(hour=0, minute=0, second=0)
blocks = db.blacklist.find({'added_at': {'$gte': today}})
```

---

## Open Design Questions

**To be decided after overnight testing**:

1. **Whitelisting Control**:
   - Should AI be allowed to whitelist domains, or only specific links?
   - Should only parents be able to whitelist domains?
   - Current: AI can whitelist both links and domains

2. **Dynamic Content Monitoring**:
   - Should extension use MutationObserver to detect AJAX/SPA content changes?
   - Example: YouTube allowed, but need to block WW2 video search results
   - Current: Only analyzes on initial page load

3. **Appeal Limits**:
   - Should children get more than 1 appeal per URL?
   - Should appeals reset after X days?
   - Current: Hard limit of 1 appeal per URL forever

---

## Troubleshooting

### Common Issues

**Extension not blocking pages**:
1. Check server is running: `curl http://localhost:5000/`
2. Check browser console for errors (F12)
3. Verify extension loaded: chrome://extensions
4. Check CORS headers in server response

**AI returning errors**:
1. Verify OPENAI_API_KEY in environment
2. Check API quota/billing: https://platform.openai.com/usage
3. Check prompt length (max 128k tokens)
4. Review prompts.py for syntax errors

**MongoDB connection failed**:
1. Check MongoDB is running: `mongosh`
2. Verify MONGO_URI in .env
3. Check network access for MongoDB Atlas
4. Verify database name: `NorthlightDB`

**Desktop worker not sending screenshots**:
1. Server endpoint doesn't exist yet (known issue)
2. Verify win32gui installed (Windows only): `pip install pywin32`
3. Run as administrator (for some windows)
4. Check API URL in active_window_test.py

**Gmail authentication failing**:
1. Verify credentials.json from Google Cloud Console
2. Enable Gmail API in Google Cloud Console
3. Delete token.pickle and re-authenticate
4. Check OAuth consent screen configuration

**Appeal submission not working**:
1. Known bug: Line 258 syntax error
2. Fix: Change `statusDiv.textContent = + data.message;` to `statusDiv.textContent = data.message;`

---

## Key Files Reference

| File Path | Purpose | Lines | Status |
|-----------|---------|-------|--------|
| `Big-Brother/new_server.py` | Main Flask API server with AI agents | 635 | ✅ Working |
| `browser-eyes/src/content-script.js` | Browser extension logic | 361 | 🐛 Has bugs |
| `Big-Brother/Agent_Tools/Email/gmail_agent.py` | Gmail integration | 389 | ✅ Complete, not integrated |
| `Big-Brother/System_Monitoring/active_window_test.py` | Desktop monitoring | 200 | ✅ Complete, server missing |
| `Big-Brother/prompts.py` | LLM prompt templates | 50 | ✅ Working |
| `browser-eyes/src/background.js` | Extension service worker | 6 | ⚠️ Minimal stub |
| `Big-Brother/email_agent.py` | Email notification stubs | 6 | ❌ Empty stubs |
| `Big-Brother/desktop_agent.py` | Desktop integration stub | 0 | ❌ Empty |

---

## Contributing Guidelines

### Code Style

**Python** (PEP 8):
- Use `snake_case` for functions and variables
- Use `PascalCase` for classes
- Type hints for function signatures
- Docstrings for all public functions

**JavaScript**:
- Use `camelCase` for variables and functions
- Use `PascalCase` for React components
- ESLint + Prettier for formatting
- Async/await for promises (no .then() chains)

### Git Workflow

**Branch Naming**:
- Feature: `feature/desktop-monitoring-integration`
- Bugfix: `bugfix/appeal-submission-syntax-error`
- Enhancement: `enhancement/ai-prompt-improvements`

**Commit Messages**:
```
feat: Add desktop screenshot endpoint
fix: Resolve appeal submission syntax error
docs: Update claude.md with correct AI models
refactor: Extract AI agent logic to separate module
test: Add integration tests for /analyze endpoint
```

---

## Version History

- **v0.2.1** (Current): Codebase analyzed, bugs identified, priorities set
- **v0.2.0**: Browser monitoring + AI agents working, desktop monitoring implemented but not integrated
- **v0.1.0**: Initial server and extension prototypes

---

**Last Updated**: 2025-11-18
**Maintained By**: VigilMind Development Team
**AI Assistant Context**: This file gives AI assistants complete context about the project for code assistance, debugging, and feature development. Updated based on actual codebase analysis.
