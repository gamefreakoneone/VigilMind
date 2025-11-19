from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient, ASCENDING
import openai
import os
import argparse
import sys
from urllib.parse import urlparse, parse_qs
import json
from datetime import datetime
import threading
import time
from agents import Agent, Runner, WebSearchTool, function_tool
import queue
from pydantic import BaseModel
import asyncio
from youtube_transcript_api import YouTubeTranscriptApi
import prompts
from email_agent import notify_parent_appeal_approved, send_approval_request_email, start_email_monitoring
import base64
import uuid

# ytt_api.fetch("6Lq3k-XQkrE")

# Database format for whitelist and blocklist: link , reason, timestamp


from System_Monitoring import active_window_test


openai.api_key = os.getenv("OPENAI_API_KEY")


app = Flask(__name__)
CORS(app)
# @app.after_request
# def after_request(response):
#     response.headers['Access-Control-Allow-Origin'] = '*'
#     response.headers['Access-Control-Allow-Headers'] = 'Content-Type'
#     response.headers['Access-Control-Allow-Methods'] = 'GET,POST,OPTIONS'
#     response.headers['Access-Control-Allow-Private-Network'] = 'true'
#     # Add these missing headers:
#     response.headers['Access-Control-Max-Age'] = '600'
#     return response

analysis_locks = {}
locks_lock = threading.Lock()

MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
client = MongoClient(MONGO_URI)
db = client["NorthlightDB"]

# # Document structure:
# {
#     'link': 'google.com' or 'google.com/really-bad-page',
#     'added_at': datetime,
#     'approval_made': 0 or 1,
#     'reason': 'AI Analysis' or 'Manual'
# }

whitelist_col = db["whitelist"]
blacklist_col = db["blacklist"]
whitelist_col.create_index([("link", ASCENDING)], unique=True)
blacklist_col.create_index([("link", ASCENDING)], unique=True)\


appeals_col = db["appeals"]
pending_approvals_col = db["pending_approvals"]

config_col = db["config"]
desktop_events_col = db[
    "desktop_events"
]  # Need to decide if I should include this or not

blacklist_desktop_col = db["blacklist_desktop"]
whitelist_desktop_col = db["whitelist_desktop"]

# whitelist_col.create_index([("link", ASCENDING)], unique=True)
# blacklist_col.create_index([("link", ASCENDING)], unique=True)

whitelist_desktop_col.create_index([("app", ASCENDING)], unique=True)
blacklist_desktop_col.create_index([("app", ASCENDING)], unique=True)

appeals_col.create_index([("link", ASCENDING)])
pending_approvals_col.create_index([("approval_id", ASCENDING)], unique=True)


# Critical system applications that should NEVER be terminated
CRITICAL_SYSTEM_APPS = [
    'explorer.exe',     # Windows Explorer/File Explorer - CRITICAL
    'taskmgr.exe',      # Task Manager
    'dwm.exe',          # Desktop Window Manager
    'chrome.exe',       # Chrome browser (monitored by extension)
    'firefox.exe',      # Firefox browser (monitored by extension)
    'msedge.exe',       # Edge browser (monitored by extension)
    'brave.exe',        # Brave browser (monitored by extension)
    'csrss.exe',        # Client/Server Runtime Subsystem
    'winlogon.exe',     # Windows Logon Process
    'services.exe',     # Services Control Manager
    'lsass.exe',        # Local Security Authority Subsystem
    'svchost.exe',      # Service Host Process
    'system',           # System process
    'smss.exe',         # Session Manager Subsystem
    'wininit.exe',      # Windows Start-Up Application
]


def initialize_critical_system_apps():
    """Initialize critical system apps in whitelist to prevent accidental termination"""
    print("Initializing critical system applications whitelist...")
    for app in CRITICAL_SYSTEM_APPS:
        try:
            # Use upsert to avoid duplicates
            whitelist_desktop_col.update_one(
                {'app': app.lower()},
                {'$set': {
                    'app': app.lower(),
                    'added_at': datetime.now(),
                    'reason': 'Critical system application',
                    'protected': True  # Mark as protected
                }},
                upsert=True
            )
            # Remove from blacklist if somehow it got there
            blacklist_desktop_col.delete_one({'app': app.lower()})
        except Exception as e:
            print(f"Warning: Could not whitelist {app}: {e}")
    print(f"Protected {len(CRITICAL_SYSTEM_APPS)} critical system applications")


# Desktop monitoring helper functions
def is_app_whitelisted(app_name):
    """Check if an app is in the whitelist"""
    return whitelist_desktop_col.find_one({'app': app_name.lower()}) is not None

def is_app_blacklisted(app_name):
    """Check if an app is in the blacklist"""
    return blacklist_desktop_col.find_one({'app': app_name.lower()}) is not None

def add_to_desktop_whitelist(app_name, reason='Manual'):
    """Add app to desktop whitelist"""
    try:
        entry = {
            "app": app_name.lower(),
            "added_at": datetime.now(),
            "reason": reason
        }
        whitelist_desktop_col.insert_one(entry)
        # Remove from blacklist if exists
        blacklist_desktop_col.delete_one({'app': app_name.lower()})
        return True
    except:
        return False

def add_to_desktop_blacklist(app_name, reason='Manual', screenshot_path=None, reasoning=None, parental_reasoning=None):
    """Add app to desktop blacklist"""
    try:
        entry = {
            "app": app_name.lower(),
            "added_at": datetime.now(),
            "reason": reason,
            "screenshot_path": screenshot_path,
            "reasoning": reasoning,
            "parental_reasoning": parental_reasoning
        }
        blacklist_desktop_col.insert_one(entry)
        # Remove from whitelist if exists
        whitelist_desktop_col.delete_one({'app': app_name.lower()})
        return True
    except:
        return False


def get_monitoring_config():
    """Fetching the aprent's configuration from the database"""
    config = config_col.find_one({"type": "monitoring_rules"})
    if not config:
        config = {
            "type": "monitoring_rules",
            "parent_email": "amogh@outlook.com",  # Insert default email here.
            "monitoring_prompt": "Block google  only.",
            "agent_can_auto_approve": False,
            "desktop_monitoring_enabled": True,
            "screenshot_interval": 120,
            "blocked_apps": ["steam.exe"],
        }
        config_col.insert_one(config)
    return config


def update_monitoring_config(new_config):
    """Update monitoring configuration"""
    config_col.update_one(
        {"type": "monitoring_rules"}, {"$set": new_config}, upsert=True
    )



def add_to_whitelist(link, reason='Manual', reasoning=None, parental_reasoning=None):
    """Add link to whitelist"""
    try:
        entry = {
            "link": link,
            "added_at": datetime.now(),
            "reason": reason
        }
        # Add new reasoning fields if provided
        if reasoning:
            entry["reasoning"] = reasoning
        if parental_reasoning:
            entry["parental_reasoning"] = parental_reasoning

        whitelist_col.insert_one(entry)
        # Remove from blacklist if exists
        blacklist_col.delete_one({'link': link})
        return True
    except:
        return False


def add_to_blacklist(link, reason='Manual', reasoning=None, parental_reasoning=None):
    """Add link to blacklist. Also add number of appeals"""
    try:
        entry = {
            "link": link,
            "appeals": 0,
            "added_at": datetime.now(),
            "reason": reason
        }
        # Add new reasoning fields if provided
        if reasoning:
            entry["reasoning"] = reasoning
        if parental_reasoning:
            entry["parental_reasoning"] = parental_reasoning

        blacklist_col.insert_one(entry)
        # Remove from whitelist if exists
        whitelist_col.delete_one({'link': link})
        return True
    except:
        return False

def is_whitelisted(link):
    return whitelist_col.find_one({'link': link}) is not None

def is_blacklisted(link):
    """Check if link is in blacklist"""
    return blacklist_col.find_one({'link': link}) is not None

def get_blacklist_entry(link):
    return blacklist_col.find_one({'link': link})



# TODO: IMplement locks for analysis to prevent multiple agents analyzing the same link at the same time. Maybe ask Claude to implement this?
# def acquire_analysis_lock(link):
#     """Try to acquire lock for analyzing a link"""
#     with locks_lock:
#         if link in analysis_locks:
#             return False  # Already being analyzed
#         analysis_locks[link] = threading.Lock()
#         analysis_locks[link].acquire()
#         return True

# def release_analysis_lock(link):
#     """Release lock for a link"""
#     with locks_lock:
#         if link in analysis_locks:
#             analysis_locks[link].release()
#             del analysis_locks[link]
# analysis_cache_col = db['analysis_cache']
# analysis_cache_col.create_index([('link', ASCENDING)])

# def get_cached_analysis(link):
#     """Get cached analysis result"""
#     cache = analysis_cache_col.find_one({'link': link})
#     if cache:
#         return cache.get('decision')
#     return None

# def cache_analysis(domain, result): # I dont think we need this
#     """Cache analysis result"""
#     analysis_cache_col.update_one(
#         {'link': link},
#         {'$set': {
#             'link': link,
#             'result': result,
#             'timestamp': datetime.now()
#         }},
#         upsert=True
#     )

# def wait_for_analysis(link, timeout=10):
#     start_time = time.time()
#     while time.time() - start_time < timeout:
#         # Check if analysis is complete (result in cache)
#         cached = get_cached_analysis(link)
#         if cached:
#             return cached
#         time.sleep(0.5)
#     return None


# Todo: Implement browser screebgit
@function_tool
def get_browser_screenshot():
    pass


@function_tool
def get_youtube_transcript(link: str) -> dict:
    """
    Extracts the transcript from a YouTube video URL.

    Args:
        link: The YouTube video URL (supports youtube.com and youtu.be formats)

    Returns:
        dict: Contains 'success' (bool), 'transcript' (str), and 'error' (str) if failed
    """
    try:
        # Extract video ID from URL
        video_id = extract_video_id(link)
        if not video_id:
            return {"success": False, "transcript": "", "error": "Invalid YouTube URL"}

        # Get transcript using the new API (v1.2.2+)
        ytt_api = YouTubeTranscriptApi()
        fetched_transcript = ytt_api.fetch(video_id)

        # Combine all transcript snippets into single text
        full_transcript = " ".join(
            [snippet.text for snippet in fetched_transcript.snippets]
        )

        return {"success": True, "transcript": full_transcript, "error": ""}

    except Exception as e:
        return {
            "success": False,
            "transcript": "",
            "error": f"Error extracting transcript: {str(e)}",
        }


def extract_video_id(link: str) -> str:
    if "youtu.be/" in link:
        return link.split("youtu.be/")[-1].split("?")[0].split("&")[0]

    # Pattern for youtube.com links
    parsed_url = urlparse(link)
    if parsed_url.hostname in ["www.youtube.com", "youtube.com", "m.youtube.com"]:
        if parsed_url.path == "/watch":
            query_params = parse_qs(parsed_url.query)
            return query_params.get("v", [None])[0]
        elif parsed_url.path.startswith("/embed/"):
            return parsed_url.path.split("/embed/")[-1].split("?")[0]
        elif parsed_url.path.startswith("/v/"):
            return parsed_url.path.split("/v/")[-1].split("?")[0]

    return None


# Remember to put this prompt in a different file
# Todo: Maybe be consider a method by which you can take a screenshot of the webpage behind the analysis wall.
# web_analysis_prompt = """
# The parent has requested the following standards for content evaluation: {parental_prompt}.
# Your task is to analyze the provided content and determine if it aligns with these standards:
# URL: {url}
# Title: {title}
# Content: {content}
# """


class web_content_analysis_JSON(BaseModel):
    link: str
    action: str  # 'approve' or 'block'
    reasoning: str  # Vague, child-safe explanation
    parental_reasoning: str  # Detailed explanation for parents


web_checker_agent = Agent(
    name="Parental Web Content Analyzer",
    instructions=prompts.web_checker_prompt,
    tools=[WebSearchTool(), get_youtube_transcript],
    output_type=web_content_analysis_JSON,
    model = "gpt-5-mini"
)


async def web_content_analysis(link, title, content):
    """This agent will analyze the content using the standards set by the parent"""
    config = get_monitoring_config()
    try:
        prompt = prompts.web_analysis_prompt.format(
            parental_prompt=config["monitoring_prompt"],
            url=link,
            title=title,
            content=content[:5000],
        )

        result = await Runner.run(web_checker_agent, prompt)
        structured = result.final_output_as(web_content_analysis_JSON)
        # response = await web_checker_agent.run(
        #     prompt=prompts.web_analysis_prompt.format(
        #         parental_prompt=config["monitoring_prompt"],
        #         url=link,
        #         title=title,
        #         content=content[:5000],
        #     )
        # )
        print(structured)
        return structured.model_dump()
    
    except Exception as e:
        print(f"ERROR during web content analysis: {e}", flush=True)
        # import traceback
        # traceback.print_exc()
        return {
            "link": link,
            "action": "block",
            "reasoning": "We couldn't check this content properly. Please try again later.",
            "parental_reasoning": "Error during analysis, review manually.",
        }

def check_webpage_against_DB(link):
    """Check if the webpage is in the whitelist or blacklist"""
    domain = urlparse(link).netloc.lower()

    bl_entry = (
        blacklist_col.find_one({"link": link})
        or blacklist_col.find_one({"link": domain})
    )

    if bl_entry:
        appeals_used = bl_entry.get("appeals", 0)
        # Support both old and new format
        reasoning = bl_entry.get("reasoning", "This content has been blocked.")
        parental_reasoning = bl_entry.get("parental_reasoning", bl_entry.get("reason", "Blacklisted"))
        return {
            "link": link,
            "action": "block",
            "reasoning": reasoning,
            "parental_reasoning": parental_reasoning,
            "appeals_used": appeals_used,
        }

    if is_whitelisted(link) or is_whitelisted(domain):
        return {
            "link": link,
            "action": "allow",
            "reasoning": "This content is approved.",
            "parental_reasoning": "URL or domain whitelisted",
            "appeals_used": 0,
        }

    return None

@app.route("/analyze", methods=["POST"])
def analyze_webpage():
    data = request.json
    link = data.get("url", "")
    title = data.get("title", "")
    content = data.get("content", "")

    config = get_monitoring_config()
    agent_can_auto_approve = config.get("agent_can_auto_approve", False)

    result = check_webpage_against_DB(link)
    if result is not None:
        result["appeal_enabled"] = True  # Always allow appeals
        result["agent_has_authority"] = agent_can_auto_approve
        return jsonify(result)

    result = asyncio.run(web_content_analysis(link, title, content))

    if result["action"] == "block":
        add_to_blacklist(
            link,
            reason=result.get("parental_reasoning", "AI Analysis"),
            reasoning=result.get("reasoning"),
            parental_reasoning=result.get("parental_reasoning")
        )
        result["appeals_used"] = 0
    else:
        add_to_whitelist(
            link,
            reason=result.get("parental_reasoning", "AI Analysis"),
            reasoning=result.get("reasoning"),
            parental_reasoning=result.get("parental_reasoning")
        )
        result["appeals_used"] = 0

    result["appeal_enabled"] = True  # Always allow appeals
    result["agent_has_authority"] = agent_can_auto_approve

    return jsonify(result)


# @app.route("/analyze", methods=["POST", "OPTIONS"])
# def analyze_webpage():
#     # Handle OPTIONS request first
#     if request.method == "OPTIONS":
#         response = app.make_response('')
#         response.status_code = 204
#         return response
    
#     data = request.json
#     link = data.get("url", "")
#     title = data.get("title", "")
#     content = data.get("content", "")

#     config = get_monitoring_config()
#     agent_can_auto_approve = config.get("agent_can_auto_approve", False)

#     result = check_webpage_against_DB(link)
#     if result is not None:
#         result["appeal_enabled"] = agent_can_auto_approve
#         return jsonify(result)

#     result = asyncio.run(web_content_analysis(link, title, content))

#     if result["action"] == "block":
#         add_to_blacklist(link, reason=result["reason"])
#         result["appeals_used"] = 0
#     else:
#         add_to_whitelist(link, reason=result["reason"])
#         result["appeals_used"] = 0

#     result["appeal_enabled"] = agent_can_auto_approve

#     return jsonify(result)

@app.route("/whitelist", methods=["GET"])
def get_whitelist():
    items = list(whitelist_col.find({}, {"_id": 0}))
    return jsonify(items)


@app.route("/blacklist", methods=["GET"])
def get_blacklist():
    items = list(blacklist_col.find({}, {"_id": 0}))
    return jsonify(items)


@app.route("/config", methods=["GET"])
def get_config():
    """Get current monitoring configuration"""
    config = get_monitoring_config()
    # Remove MongoDB _id field if present
    config.pop("_id", None)
    return jsonify(config)


@app.route("/config", methods=["PUT"])
def update_config():
    """Update monitoring configuration"""
    data = request.json

    # Validate required fields
    if "parent_email" not in data or "monitoring_prompt" not in data:
        return jsonify({"ok": False, "error": "Missing required fields"}), 400

    # Check if monitoring prompt has changed
    old_config = get_monitoring_config()
    prompt_changed = old_config.get("monitoring_prompt") != data.get("monitoring_prompt")

    new_config = {
        "type": "monitoring_rules",
        "parent_email": data.get("parent_email"),
        "monitoring_prompt": data.get("monitoring_prompt"),
        "agent_can_auto_approve": data.get("agent_can_auto_approve", False),
        "desktop_monitoring_enabled": data.get("desktop_monitoring_enabled", True),
        "screenshot_interval": data.get("screenshot_interval", 120),
        "blocked_apps": data.get("blocked_apps", []),
    }

    update_monitoring_config(new_config)

    # If monitoring prompt changed, clear AI-generated lists
    if prompt_changed:
        print("Monitoring prompt changed - clearing AI-generated lists...")

        # Clear web blacklist (AI-generated only)
        result = blacklist_col.delete_many({"reason": {"$in": ["AI Analysis", "Appeal auto-approved"]}})
        print(f"Removed {result.deleted_count} AI-generated blacklist entries")

        # Clear web whitelist (AI-generated only, keep manually added)
        result = whitelist_col.delete_many({"reason": {"$in": ["AI Analysis", "Appeal auto-approved"]}})
        print(f"Removed {result.deleted_count} AI-generated whitelist entries")

        # Clear desktop blacklist (AI-generated only)
        result = blacklist_desktop_col.delete_many({"reason": "AI Analysis"})
        print(f"Removed {result.deleted_count} AI-generated desktop blacklist entries")

        # Reinitialize critical system apps
        initialize_critical_system_apps()

        return jsonify({
            "ok": True,
            "message": "Configuration updated successfully. AI-generated lists cleared to apply new guidelines."
        })

    return jsonify({"ok": True, "message": "Configuration updated successfully"})


@app.route("/whitelist", methods=["POST"])
def add_to_whitelist_endpoint():
    """Add domain to whitelist"""
    data = request.json
    domain = data.get("domain", "").strip().lower()

    if not domain:
        return jsonify({"ok": False, "error": "Domain is required"}), 400

    if add_to_whitelist(domain, reason="Parent added"):
        return jsonify({"ok": True, "message": f"Added {domain} to whitelist"})
    else:
        return jsonify({"ok": False, "error": "Domain already in whitelist"}), 409


@app.route("/whitelist/<path:domain>", methods=["DELETE"])
def remove_from_whitelist(domain):
    """Remove domain from whitelist"""
    domain = domain.strip().lower()
    result = whitelist_col.delete_one({"link": domain})

    if result.deleted_count > 0:
        return jsonify({"ok": True, "message": f"Removed {domain} from whitelist"})
    else:
        return jsonify({"ok": False, "error": "Domain not found in whitelist"}), 404


@app.route("/blacklist", methods=["POST"])
def add_to_blacklist_endpoint():
    """Add domain to blacklist"""
    data = request.json
    domain = data.get("domain", "").strip().lower()

    if not domain:
        return jsonify({"ok": False, "error": "Domain is required"}), 400

    if add_to_blacklist(domain, reason="Parent added"):
        return jsonify({"ok": True, "message": f"Added {domain} to blacklist"})
    else:
        return jsonify({"ok": False, "error": "Domain already in blacklist"}), 409


@app.route("/blacklist/<path:domain>", methods=["DELETE"])
def remove_from_blacklist(domain):
    """Remove domain from blacklist"""
    domain = domain.strip().lower()
    result = blacklist_col.delete_one({"link": domain})

    if result.deleted_count > 0:
        return jsonify({"ok": True, "message": f"Removed {domain} from blacklist"})
    else:
        return jsonify({"ok": False, "error": "Domain not found in blacklist"}), 404


@app.route("/pending-approvals", methods=["GET"])
def get_pending_approvals():
    """Get all pending parent approvals"""
    approvals = list(pending_approvals_col.find(
        {"status": "awaiting_parent"},
        {"_id": 0}
    ).sort("timestamp", -1))

    return jsonify(approvals)


@app.route("/approve-appeal", methods=["POST"])
def approve_appeal():
    """Parent approves a pending appeal"""
    data = request.json
    approval_id = data.get("approval_id", "")

    if not approval_id:
        return jsonify({"ok": False, "error": "approval_id is required"}), 400

    # Find the pending approval
    approval = pending_approvals_col.find_one({"approval_id": approval_id})
    if not approval:
        return jsonify({"ok": False, "error": "Approval request not found"}), 404

    if approval.get("status") != "awaiting_parent":
        return jsonify({"ok": False, "error": "This approval has already been processed"}), 409

    link = approval.get("link")

    # Add to whitelist and remove from blacklist
    add_to_whitelist(link, reason="Parent approved appeal")

    # Update the appeal status
    appeals_col.update_one(
        {"appeal_id": approval.get("appeal_id")},
        {"$set": {"status": "parent_approved", "resolved_at": datetime.now()}}
    )

    # Update pending approval status
    pending_approvals_col.update_one(
        {"approval_id": approval_id},
        {"$set": {"status": "approved", "resolved_at": datetime.now()}}
    )

    return jsonify({"ok": True, "message": f"Appeal approved for {link}"})


@app.route("/deny-appeal", methods=["POST"])
def deny_appeal():
    """Parent denies a pending appeal"""
    data = request.json
    approval_id = data.get("approval_id", "")

    if not approval_id:
        return jsonify({"ok": False, "error": "approval_id is required"}), 400

    # Find the pending approval
    approval = pending_approvals_col.find_one({"approval_id": approval_id})
    if not approval:
        return jsonify({"ok": False, "error": "Approval request not found"}), 404

    if approval.get("status") != "awaiting_parent":
        return jsonify({"ok": False, "error": "This approval has already been processed"}), 409

    # Update the appeal status
    appeals_col.update_one(
        {"appeal_id": approval.get("appeal_id")},
        {"$set": {"status": "parent_denied", "resolved_at": datetime.now()}}
    )

    # Update pending approval status
    pending_approvals_col.update_one(
        {"approval_id": approval_id},
        {"$set": {"status": "denied", "resolved_at": datetime.now()}}
    )

    return jsonify({"ok": True, "message": "Appeal denied"})


# Reference:
#   const pageData = {
#     url: window.location.href,
#     title: document.title,
#     content: article ? article.textContent : document.body.innerText,
#     timestamp: Date.now(),
#   };


class Final_Appeal_JSON(BaseModel):
    link: str
    action: str  # 'approve' or 'block'
    reasoning: str  # Vague, child-safe explanation
    parental_reasoning: str  # Detailed explanation for parents


appeal_agent = Agent(
    name="Appeal agent",
    instructions=prompts.appeals_prompt,
    tools=[WebSearchTool(), get_youtube_transcript],
    output_type=Final_Appeal_JSON,
)


class Desktop_Analysis_JSON(BaseModel):
    action: str  # 'ok' or 'block'
    reasoning: str  # Vague, child-safe explanation (empty if ok)
    parental_reasoning: str  # Detailed explanation for parents


desktop_monitor_agent = Agent(
    name="Desktop Application Monitor",
    instructions=prompts.desktop_monitoring_prompt,
    output_type=Desktop_Analysis_JSON,
    model="gpt-4.1-mini"
)

async def evaluate_appeal_with_llm(link, title, previous_evaluation_reason  , appeal_reason, monitoring_prompt):
    try:
        prompt = prompts.appeals_prompt.format(
            parental_prompt=monitoring_prompt,
                url=link,
                title=title,
                past_reasoning=previous_evaluation_reason,
                appeal_reason=appeal_reason
        )
        result = await Runner.run(appeal_agent, prompt)
        structured = result.final_output_as(Final_Appeal_JSON)
        # response = await appeal_agent.run(
        #     prompt=prompts.appeals_prompt.format(
        #         parental_prompt=monitoring_prompt,
        #         url=link,
        #         title=title,
        #         past_reasoning=previous_evaluation_reason,
        #         appeal_reason=appeal_reason,
        #     )
        # )
        # return response.final_output.model_dump()
        return structured.model_dump()
    except Exception as e:
        print(f"Error during web content analysis: {e}")
        return {
            "link": link,
            "action": "block",
            "reasoning": "We couldn't review your appeal properly. Please try again later.",
            "parental_reasoning": "Error during analysis, review manually.",
        }
    pass


async def analyze_desktop_screenshot(app_name, window_title, image_data_url, monitoring_prompt):
    """Analyze desktop screenshot using vision agent"""
    try:
        prompt = prompts.desktop_monitoring_prompt.format(
            parental_prompt=monitoring_prompt,
            app_name=app_name,
            window_title=window_title
        )

        input_items = [{
            "role": "user",
            "content": [
                {"type": "input_text", "text": prompt},
                {"type": "input_image", "image_url": image_data_url}
            ]
        }]

        result = await Runner.run(desktop_monitor_agent, input=input_items)
        structured = result.final_output_as(Desktop_Analysis_JSON)
        return structured.model_dump()

    except Exception as e:
        print(f"ERROR during desktop screenshot analysis: {e}", flush=True)
        return {
            "action": "ok",
            "reasoning": "",
            "parental_reasoning": f"Error during analysis: {str(e)}"
        }


@app.route("/appeal", methods=["POST"])
def submit_appeal():
    """Child submits appeal for blocked content"""
    data = request.json
    link = data.get("url", "")
    appeal_reason = data.get("appeal_reason", "")
    title = data.get("title", "")

    domain = urlparse(link).netloc.lower()
    config = get_monitoring_config()
    agent_can_auto_approve = config.get("agent_can_auto_approve", False)

    entry = blacklist_col.find_one({"link": link})
    if not entry:
        return jsonify({
            "ok": False,
            "error": "URL is not blacklisted, nothing to appeal."
        }), 400

    appeals_used = entry.get("appeals", 0)
    if appeals_used >= 1:
        return jsonify({
            "ok": False,
            "error": "Appeal already used for this URL."
        }), 403

    appeal_id = f"appeal_{int(time.time())}"
    appeals_col.insert_one({
        "appeal_id": appeal_id,
        "link": link,
        "domain": domain,
        "child_reason": appeal_reason,
        "timestamp": datetime.now(),
        "status": "pending",
    })

    # Mark that an appeal was used
    blacklist_col.update_one(
        {"_id": entry["_id"]},
        {
            "$inc": {"appeals": 1},
            "$set": {
                "last_appeal_at": datetime.now(),
                "last_appeal_message": appeal_reason,
            },
        },
    )

    # SCENARIO 2: Agent does NOT have auto-approve authority
    # Skip AI evaluation and go directly to parent
    if not agent_can_auto_approve:
        approval_id = f"approval_{int(time.time())}"
        pending_approvals_col.insert_one({
            "approval_id": approval_id,
            "appeal_id": appeal_id,
            "link": link,
            "domain": domain,
            "child_reason": appeal_reason,
            "timestamp": datetime.now(),
            "status": "awaiting_parent",
        })

        appeals_col.update_one(
            {"appeal_id": appeal_id},
            {"$set": {"status": "awaiting_parent"}},
        )

        send_approval_request_email(approval_id, link, appeal_reason)

        return jsonify({
            "ok": True,
            "status": "pending_parent",
            "action": "block",
            "reason": "Your request has been sent to your parent for approval.",
        })

    # SCENARIO 1: Agent HAS auto-approve authority
    # Let AI evaluate first
    # Use parental_reasoning from entry, fallback to old "reason" field for backward compatibility
    past_reasoning = entry.get("parental_reasoning", entry.get("reason", "Previously blocked"))
    decision = asyncio.run(evaluate_appeal_with_llm(link, title, past_reasoning, appeal_reason, config["monitoring_prompt"]))

    # Update blacklist with AI decision (store both reasoning types)
    blacklist_col.update_one(
        {"_id": entry["_id"]},
        {"$set": {
            "last_appeal_llm_reasoning": decision.get("reasoning"),
            "last_appeal_llm_parental_reasoning": decision.get("parental_reasoning")
        }},
    )

    if decision["action"] == "approve":
        # AI approved the appeal
        whitelist_col.insert_one({
            "link": link,
            "added_at": datetime.now(),
            "reason": f"Appeal auto-approved: {decision.get('parental_reasoning')}",
            "reasoning": decision.get("reasoning"),
            "parental_reasoning": decision.get("parental_reasoning"),
        })
        blacklist_col.delete_one({"link": link})

        appeals_col.update_one(
            {"appeal_id": appeal_id},
            {"$set": {
                "status": "auto_approved",
                "agent_decision": decision.get("parental_reasoning"),
                "reasoning": decision.get("reasoning")
            }},
        )

        notify_parent_appeal_approved(link, appeal_reason, decision.get("parental_reasoning"))

        return jsonify({
            "ok": True,
            "status": "approved",
            "action": "allow",
            "reasoning": decision.get("reasoning"),  # Child-safe message
            "reload": True,
        })

    # AI denied the appeal - offer escalation to parent
    appeals_col.update_one(
        {"appeal_id": appeal_id},
        {"$set": {
            "status": "ai_denied",
            "agent_decision": decision.get("parental_reasoning"),
            "reasoning": decision.get("reasoning")
        }},
    )

    return jsonify({
        "ok": True,
        "status": "ai_denied",
        "action": "block",
        "reasoning": decision.get("reasoning"),  # Child-safe message
        "can_escalate": True,
        "appeal_id": appeal_id,
    })


@app.route("/escalate-to-parent", methods=["POST"])
def escalate_to_parent():
    """Child escalates to parent after AI denied the appeal"""
    data = request.json
    appeal_id = data.get("appeal_id", "")
    link = data.get("url", "")
    appeal_reason = data.get("appeal_reason", "")

    # Verify the appeal exists and was AI-denied
    appeal = appeals_col.find_one({"appeal_id": appeal_id})
    if not appeal:
        return jsonify({
            "ok": False,
            "error": "Appeal not found."
        }), 400

    if appeal.get("status") != "ai_denied":
        return jsonify({
            "ok": False,
            "error": "This appeal cannot be escalated."
        }), 403

    domain = urlparse(link).netloc.lower()

    # Create pending approval for parent review
    approval_id = f"approval_{int(time.time())}"
    pending_approvals_col.insert_one({
        "approval_id": approval_id,
        "appeal_id": appeal_id,
        "link": link,
        "domain": domain,
        "child_reason": appeal_reason,
        "timestamp": datetime.now(),
        "status": "awaiting_parent",
        "escalated_from_ai": True,
        "ai_decision": appeal.get("agent_decision", ""),
    })

    # Update appeal status
    appeals_col.update_one(
        {"appeal_id": appeal_id},
        {"$set": {"status": "escalated_to_parent"}},
    )

    # Send email to parent
    send_approval_request_email(approval_id, link, appeal_reason)

    return jsonify({
        "ok": True,
        "status": "pending_parent",
        "action": "block",
        "reason": "Your request has been sent to your parent for review.",
    })



"""Initialize the monitoring configuration for the parent"""
@app.route("/initialize", methods=["POST"])
def initialize_monitoring():
    data = request.json
    parent_email = data.get("parent_email", "")
    monitoring_prompt = data.get("monitoring_prompt", "")
    agent_can_auto_approve = data.get("agent_can_auto_approve", False)
    desktop_monitoring_enabled = data.get("desktop_monitoring_enabled", True)
    # screenshot_interval = data.get("screenshot_interval", 120) # I dont think we should expose this to the parent either. Set it up manually
    screenshot_interval = 120
    blocked_apps = data.get("blocked_apps", []) # Should we even expose this to the parent and just let agent decide to ? 

    new_config = {
        "type": "monitoring_rules",
        "parent_email": parent_email,
        "monitoring_prompt": monitoring_prompt,
        "agent_can_auto_approve": agent_can_auto_approve,
        "desktop_monitoring_enabled": desktop_monitoring_enabled,
        "screenshot_interval": screenshot_interval,
        "blocked_apps": blocked_apps,
    }
    update_monitoring_config(new_config)
    return jsonify({"status": "success", "message": "Monitoring configuration initialized."})


# Desktop monitoring endpoints
@app.route("/desktop/screenshot", methods=["POST"])
def analyze_desktop_app():
    """Analyze desktop application screenshot"""
    data = request.json
    app_name = data.get("app_name", "")
    window_title = data.get("window_title", "")
    screenshot_base64 = data.get("screenshot", "")

    if not app_name or not screenshot_base64:
        return jsonify({"action": "ok", "reason": "Missing required data"}), 400

    # Check if app is whitelisted
    if is_app_whitelisted(app_name):
        return jsonify({
            "action": "ok",
            "reason": "Application is whitelisted"
        })

    # Check if app is already blacklisted
    if is_app_blacklisted(app_name):
        return jsonify({
            "action": "terminate",
            "reason": "Application has been blocked by parental settings. Please wait for parental approval."
        })

    # Get monitoring config
    config = get_monitoring_config()
    monitoring_prompt = config.get("monitoring_prompt", "")

    # Convert base64 to data URL for vision API
    image_data_url = f"data:image/png;base64,{screenshot_base64}"

    # Analyze screenshot with vision agent
    result = asyncio.run(analyze_desktop_screenshot(
        app_name, window_title, image_data_url, monitoring_prompt
    ))

    if result["action"] == "block":
        # Generate unique image ID
        image_id = str(uuid.uuid4())

        # Create screenshots directory if it doesn't exist
        screenshots_dir = os.path.join(os.path.dirname(__file__), "screenshots")
        os.makedirs(screenshots_dir, exist_ok=True)

        # Save screenshot
        screenshot_path = os.path.join(screenshots_dir, f"{image_id}.png")
        try:
            with open(screenshot_path, "wb") as f:
                f.write(base64.b64decode(screenshot_base64))
        except Exception as e:
            print(f"Error saving screenshot: {e}")
            screenshot_path = None

        # Add to blacklist
        add_to_desktop_blacklist(
            app_name,
            reason="AI Analysis",
            screenshot_path=screenshot_path,
            reasoning=result.get("reasoning"),
            parental_reasoning=result.get("parental_reasoning")
        )

        return jsonify({
            "action": "terminate",
            "reason": result.get("reasoning", "This application may violate parental guidelines. Please wait for parental approval.")
        })

    return jsonify({
        "action": "allow",
        "reason": ""
    })


@app.route("/desktop/whitelist", methods=["GET"])
def get_desktop_whitelist():
    """Get all whitelisted desktop apps"""
    items = list(whitelist_desktop_col.find({}, {"_id": 0}))
    return jsonify(items)


@app.route("/desktop/blacklist", methods=["GET"])
def get_desktop_blacklist():
    """Get all blacklisted desktop apps"""
    items = list(blacklist_desktop_col.find({}, {"_id": 0}))
    return jsonify(items)


@app.route("/desktop/whitelist", methods=["POST"])
def add_to_desktop_whitelist_endpoint():
    """Add app to desktop whitelist"""
    data = request.json
    app_name = data.get("app_name", "").strip().lower()

    if not app_name:
        return jsonify({"ok": False, "error": "App name is required"}), 400

    if add_to_desktop_whitelist(app_name, reason="Parent added"):
        return jsonify({"ok": True, "message": f"Added {app_name} to whitelist"})
    else:
        return jsonify({"ok": False, "error": "App already in whitelist"}), 409


@app.route("/desktop/blacklist/<path:app_name>", methods=["DELETE"])
def remove_from_desktop_blacklist(app_name):
    """Remove app from desktop blacklist (approve)"""
    app_name = app_name.strip().lower()

    # Get the entry to find screenshot path
    entry = blacklist_desktop_col.find_one({"app": app_name})

    # Delete the entry
    result = blacklist_desktop_col.delete_one({"app": app_name})

    if result.deleted_count > 0:
        # Optionally delete the screenshot file
        if entry and entry.get("screenshot_path"):
            try:
                if os.path.exists(entry["screenshot_path"]):
                    os.remove(entry["screenshot_path"])
            except Exception as e:
                print(f"Error deleting screenshot: {e}")

        return jsonify({"ok": True, "message": f"Approved {app_name}"})
    else:
        return jsonify({"ok": False, "error": "App not found in blacklist"}), 404


@app.route("/desktop/screenshot/<image_id>", methods=["GET"])
def get_screenshot(image_id):
    """Get screenshot image by ID"""
    screenshots_dir = os.path.join(os.path.dirname(__file__), "screenshots")
    screenshot_path = os.path.join(screenshots_dir, f"{image_id}.png")

    if not os.path.exists(screenshot_path):
        return jsonify({"error": "Screenshot not found"}), 404

    try:
        with open(screenshot_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode()
        return jsonify({"image": f"data:image/png;base64,{image_data}"})
    except Exception as e:
        return jsonify({"error": f"Error reading screenshot: {str(e)}"}), 500


@app.route("/health", methods=["GET"])
def health_check():
    """Health check endpoint for desktop monitor"""
    return jsonify({"status": "ok"})


def main():
    """
    Entry point for the service. Validates configuration and starts the Flask app.
    """
    parser = argparse.ArgumentParser(description="Northlight content filter API")
    parser.add_argument("--host", default=os.getenv("HOST", "127.0.0.1"),
                        help="Host interface to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "5000")),
                        help="Port to bind (default: 5000)")
    parser.add_argument("--debug", action="store_true",
                        help="Enable Flask debug mode")
    args = parser.parse_args()

    # --- Validate critical env/config ---
    if not openai.api_key:
        print("WARNING: OPENAI_API_KEY not set. LLM checks will fail.", file=sys.stderr)

    # --- Check Mongo connectivity early (fast fail) ---
    try:
        client.admin.command("ping")
        print("MongoDB connection successful.")
    except Exception as e:
        print(f"ERROR: Could not connect to MongoDB at {MONGO_URI}\\n{e}", file=sys.stderr)
        sys.exit(1)

    # --- Initialize monitoring config with defaults if it doesn't exist ---
    print("Initializing default monitoring configuration...")
    get_monitoring_config()
    print("Monitoring configuration initialized.")

    # --- Initialize critical system apps whitelist ---
    initialize_critical_system_apps()

    # --- Start Email Monitoring Service ---
    print("Starting email monitoring service...")
    start_email_monitoring(check_interval=60)  # Check inbox every 60 seconds
    print("Email monitoring service initialized.")

    # --- Start Flask app ---
    print(f"Starting server on {args.host}:{args.port}...")
    app.run(host=args.host, port=args.port, debug=args.debug)

if __name__ == "__main__":
    main()

