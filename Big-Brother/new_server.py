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
from email_agent import notify_parent_appeal_approved, send_approval_request_email

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


def get_monitoring_config():
    """Fetching the aprent's configuration from the database"""
    config = config_col.find_one({"type": "monitoring_rules"})
    if not config:
        config = {
            "type": "monitoring_rules",
            "parent_email": "",  # Insert default email here.
            "monitoring_prompt": "Block mangadex  only. But allow him to access the site if he says he wants to read One punch man.",
            "agent_can_auto_approve": True,
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



def add_to_whitelist(link, reason='Manual'):
    """Add link to whitelist"""
    try:
        whitelist_col.insert_one({
            "link": link,
            "added_at": datetime.now(),
            "reason": reason
        })
        # Remove from blacklist if exists
        blacklist_col.delete_one({'link': link})
        return True
    except:
        return False
    

def add_to_blacklist(link, reason='Manual'):
    """Add link to blacklist. Also add number of appeals"""
    try:
        blacklist_col.insert_one({
            "link": link,
            "appeals": 0,
            "added_at": datetime.now(),
            "reason": reason
        })
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
    reason: str


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
            "reason": "Error during analysis, review manually.",
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
        return {
            "link": link,
            "action": "block",
            "reason": bl_entry.get("reason", "Blacklisted"),
            "appeals_used": appeals_used,
        }

    if is_whitelisted(link) or is_whitelisted(domain):
        return {
            "link": link,
            "action": "allow",
            "reason": "URL or domain whitelisted",
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
        result["appeal_enabled"] = agent_can_auto_approve
        return jsonify(result)

    result = asyncio.run(web_content_analysis(link, title, content))

    if result["action"] == "block":
        add_to_blacklist(link, reason=result["reason"])
        result["appeals_used"] = 0
    else:
        add_to_whitelist(link, reason=result["reason"])
        result["appeals_used"] = 0

    result["appeal_enabled"] = agent_can_auto_approve

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
    reason: str


appeal_agent = Agent(
    name="Appeal agent",
    instructions=prompts.appeals_prompt,
    tools=[WebSearchTool(), get_youtube_transcript],
    output_type=Final_Appeal_JSON,
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
            "reason": "Error during analysis, review manually.",
        }
    pass

@app.route("/appeal", methods=["POST"])
def submit_appeal():
    """Child submits appeal for blocked content"""
    data = request.json
    link = data.get("url", "")
    appeal_reason = data.get("appeal_reason", "")
    title = data.get("title", "")

    domain = urlparse(link).netloc.lower()
    config = get_monitoring_config()

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

    decision = asyncio.run(evaluate_appeal_with_llm(link, title, entry["reason"],  appeal_reason, config["monitoring_prompt"]))
    # expected shape: {"should_auto_approve": True/False, "reason": "..."}

    # 5. Mark that an appeal was used, and log the result
    blacklist_col.update_one(
        {"_id": entry["_id"]},
        {
            "$inc": {"appeals": 1},
            "$set": {
                "last_appeal_at": datetime.now(),
                "last_appeal_message": appeal_reason,
                "last_appeal_llm_reason": decision.get("reason"),
            },
        },
    )

    if decision["action"]=="approve":
        whitelist_col.insert_one({
            "link": link,
            "added_at": datetime.now(),
            "reason": f"Appeal auto-approved: {decision['reason']}",
        })
        blacklist_col.delete_one({"link": link})

        appeals_col.update_one(
            {"appeal_id": appeal_id},
            {"$set": {"status": "auto_approved", "agent_decision": decision["reason"]}},
        )

        notify_parent_appeal_approved(link, appeal_reason, decision["reason"]) #TODO: Implement this function to send an email notification to the parent about the appeal approval

        return jsonify({
            "ok": True,
            "status": "approved",
            "action": "allow",
            "reason": decision["reason"],
            "reload": True,
        })

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

    send_approval_request_email(approval_id, link, appeal_reason) # TODO: Implement this function to send an email to the parent with the appeal details and they can either respond or go to a dashboard to approve or block the content.

    return jsonify({
        "ok": True,
        "status": "pending",
        "action": "block",
        "reason": "Your appeal has been sent to your parent for review.",
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

    # --- Start Flask app ---
    print(f"Starting server on {args.host}:{args.port}...")
    app.run(host=args.host, port=args.port, debug=args.debug)

if __name__ == "__main__":
    main()

