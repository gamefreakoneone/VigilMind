"""
Email Agent - Handles all email communications with parents
Responsibilities:
1. Send notifications when appeals are auto-approved
2. Send approval requests when child appeals need parent review
3. Monitor inbox for parent responses
4. Process parent responses and update whitelist/blacklist accordingly
"""

import os
import threading
import time
from typing import Dict, Optional
from datetime import datetime
from pymongo import MongoClient
from agents import Agent, Runner
from pydantic import BaseModel
import asyncio
import re

# Import Gmail Agent
from Agent_Tools.Email.gmail_agent import GmailAgent

# MongoDB connection
MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017/")
client = MongoClient(MONGO_URI)
db = client["NorthlightDB"]

pending_approvals_col = db["pending_approvals"]
whitelist_col = db["whitelist"]
blacklist_col = db["blacklist"]
config_col = db["config"]
appeals_col = db["appeals"]

# Gmail Agent instance (will be initialized when needed)
_gmail_agent = None
_monitoring_thread = None
_monitoring_active = False


def get_gmail_agent():
    """Get or create Gmail Agent singleton"""
    global _gmail_agent
    if _gmail_agent is None:
        _gmail_agent = GmailAgent()
    return _gmail_agent


def get_parent_email():
    """Get parent email from config"""
    config = config_col.find_one({"type": "monitoring_rules"})
    if config and config.get("parent_email"):
        return config["parent_email"]
    return None


# ==================== EMAIL RESPONSE PARSING AGENT ====================

class EmailResponseJSON(BaseModel):
    decision: str  # 'approve' or 'deny'
    approval_id: str  # The approval ID being responded to
    confidence: str  # 'high', 'medium', 'low'
    reasoning: str  # Brief reasoning for the decision


email_response_agent = Agent(
    name="Email Response Parser",
    instructions="""You are an AI assistant that parses parent email responses to approval requests.

Your task is to analyze the parent's email and determine:
1. Whether they are approving or denying the request
2. The approval ID they are responding to (found in the email subject or body)
3. Your confidence level in this decision

Look for keywords like:
- Approve: "yes", "approve", "allow", "ok", "fine", "go ahead", "permitted"
- Deny: "no", "deny", "block", "reject", "not allowed", "denied"

The approval ID will typically be in the format: approval_XXXXXXXXXX

Output your decision in the required JSON format.""",
    output_type=EmailResponseJSON,
    model="gpt-5-mini"
)


async def parse_parent_response(email_subject: str, email_body: str) -> Optional[EmailResponseJSON]:
    """Parse parent email response to determine approval/denial"""
    try:
        prompt = f"""
        Email Subject: {email_subject}
        Email Body: {email_body}

        Parse this email and determine if the parent is approving or denying the request.
        Extract the approval_id from the email.
        """

        result = await Runner.run(email_response_agent, prompt)
        structured = result.final_output_as(EmailResponseJSON)
        return structured
    except Exception as e:
        print(f"Error parsing parent response: {e}")
        return None


# ==================== EMAIL SENDING FUNCTIONS ====================

def notify_parent_appeal_approved(link: str, appeal_reason: str, decision_reason: str):
    """
    Send notification to parent when appeal is auto-approved

    Args:
        link: The URL that was approved
        appeal_reason: Child's reason for appealing
        decision_reason: AI agent's reason for auto-approval
    """
    try:
        parent_email = get_parent_email()
        if not parent_email:
            print("WARNING: No parent email configured. Cannot send notification.")
            return

        gmail = get_gmail_agent()

        subject = f"VigilMind: Appeal Auto-Approved for {link}"

        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #333;">
            <h2 style="color: #4CAF50;">Appeal Auto-Approved</h2>

            <p>Your child submitted an appeal for a blocked website, and our AI agent has automatically approved it based on your monitoring guidelines.</p>

            <div style="background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <p><strong>Website:</strong> <a href="{link}">{link}</a></p>
                <p><strong>Child's Reason:</strong> {appeal_reason}</p>
                <p><strong>AI Decision:</strong> {decision_reason}</p>
            </div>

            <p>The website has been automatically whitelisted and your child can now access it.</p>

            <p style="color: #666; font-size: 12px; margin-top: 30px;">
                This is an automated notification from VigilMind Parental Control System.
            </p>
        </body>
        </html>
        """

        result = gmail.send_email(to=parent_email, subject=subject, body=body)

        if result['success']:
            print(f"✅ Auto-approval notification sent to {parent_email}")
        else:
            print(f"❌ Failed to send notification: {result.get('error')}")

    except Exception as e:
        print(f"Error sending auto-approval notification: {e}")


def send_approval_request_email(approval_id: str, link: str, appeal_reason: str):
    """
    Send email to parent requesting approval for an appeal
    Parent can respond via email to approve/deny

    Args:
        approval_id: Unique ID for this approval request
        link: The URL being appealed
        appeal_reason: Child's reason for the appeal
    """
    try:
        parent_email = get_parent_email()
        if not parent_email:
            print("WARNING: No parent email configured. Cannot send approval request.")
            return

        # Get the original blocking reason
        blacklist_entry = blacklist_col.find_one({"link": link})
        blocking_reason = blacklist_entry.get("reason", "Not specified") if blacklist_entry else "Not specified"

        gmail = get_gmail_agent()

        subject = f"VigilMind: Approval Needed [{approval_id}]"

        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #333;">
            <h2 style="color: #FF9800;">Approval Request from Your Child</h2>

            <p>Your child has submitted an appeal for a blocked website. The AI agent needs your decision on whether to approve this request.</p>

            <div style="background-color: #fff3e0; padding: 15px; border-radius: 5px; margin: 20px 0; border-left: 4px solid #FF9800;">
                <p><strong>Website:</strong> <a href="{link}">{link}</a></p>
                <p><strong>Original Blocking Reason:</strong> {blocking_reason}</p>
                <p><strong>Child's Appeal Reason:</strong> {appeal_reason}</p>
            </div>

            <div style="background-color: #e3f2fd; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <h3 style="color: #1976D2;">How to Respond:</h3>
                <p><strong>Simply reply to this email with one of the following:</strong></p>
                <ul>
                    <li><strong>"APPROVE"</strong> or <strong>"YES"</strong> - to allow access to this website</li>
                    <li><strong>"DENY"</strong> or <strong>"NO"</strong> - to keep the website blocked</li>
                </ul>
                <p style="font-size: 12px; color: #666;">Our AI agent will automatically process your response and update the access accordingly.</p>
            </div>

            <p style="color: #666; font-size: 11px; margin-top: 30px;">
                <strong>Reference ID:</strong> {approval_id}<br>
                This is an automated request from VigilMind Parental Control System.
            </p>
        </body>
        </html>
        """

        result = gmail.send_email(to=parent_email, subject=subject, body=body)

        if result['success']:
            print(f"✅ Approval request sent to {parent_email} for {link}")
        else:
            print(f"❌ Failed to send approval request: {result.get('error')}")

    except Exception as e:
        print(f"Error sending approval request: {e}")


# ==================== INBOX MONITORING & PROCESSING ====================

def extract_approval_id(text: str) -> Optional[str]:
    """Extract approval ID from email text using regex"""
    # Look for pattern like approval_1234567890
    match = re.search(r'approval_\d+', text)
    if match:
        return match.group(0)
    return None


def process_parent_response(message: Dict):
    """
    Process a parent's email response to an approval request

    Args:
        message: Email message dictionary from Gmail API
    """
    try:
        subject = message.get('subject', '')
        body = message.get('body', '')

        # Extract approval ID
        approval_id = extract_approval_id(subject) or extract_approval_id(body)

        if not approval_id:
            print(f"⚠️ Could not find approval ID in email from {message.get('from')}")
            return

        # Check if this approval request exists
        approval_request = pending_approvals_col.find_one({"approval_id": approval_id})

        if not approval_request:
            print(f"⚠️ No pending approval found for ID: {approval_id}")
            return

        # Check if already processed
        if approval_request.get("status") != "awaiting_parent":
            print(f"⚠️ Approval {approval_id} already processed")
            return

        # Parse parent's response using AI agent
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        parsed_response = loop.run_until_complete(parse_parent_response(subject, body))
        loop.close()

        if not parsed_response:
            print(f"❌ Failed to parse parent response for {approval_id}")
            return

        link = approval_request.get("link")
        appeal_id = approval_request.get("appeal_id")

        if parsed_response.decision.lower() == "approve":
            # Parent approved - add to whitelist
            whitelist_col.insert_one({
                "link": link,
                "added_at": datetime.now(),
                "reason": f"Parent approved via email: {parsed_response.reasoning}"
            })

            # Remove from blacklist
            blacklist_col.delete_one({"link": link})

            # Update pending approval status
            pending_approvals_col.update_one(
                {"approval_id": approval_id},
                {"$set": {
                    "status": "parent_approved",
                    "parent_response": body,
                    "processed_at": datetime.now()
                }}
            )

            # Update appeal status
            if appeal_id:
                appeals_col.update_one(
                    {"appeal_id": appeal_id},
                    {"$set": {"status": "parent_approved"}}
                )

            print(f"✅ Parent APPROVED {link} - Added to whitelist")

            # Send confirmation email
            send_parent_confirmation(approval_id, link, "approved")

        else:  # deny
            # Update pending approval status
            pending_approvals_col.update_one(
                {"approval_id": approval_id},
                {"$set": {
                    "status": "parent_denied",
                    "parent_response": body,
                    "processed_at": datetime.now()
                }}
            )

            # Update appeal status
            if appeal_id:
                appeals_col.update_one(
                    {"appeal_id": appeal_id},
                    {"$set": {"status": "parent_denied"}}
                )

            print(f"✅ Parent DENIED {link} - Keeping blocked")

            # Send confirmation email
            send_parent_confirmation(approval_id, link, "denied")

        # Mark email as read
        gmail = get_gmail_agent()
        gmail.mark_as_read(message['id'])

    except Exception as e:
        print(f"Error processing parent response: {e}")
        import traceback
        traceback.print_exc()


def send_parent_confirmation(approval_id: str, link: str, decision: str):
    """Send confirmation email to parent after processing their response"""
    try:
        parent_email = get_parent_email()
        if not parent_email:
            return

        gmail = get_gmail_agent()

        if decision == "approved":
            subject = f"✅ Confirmed: Website Approved [{approval_id}]"
            color = "#4CAF50"
            status_text = "APPROVED"
            message_text = f"The website <strong>{link}</strong> has been whitelisted and your child can now access it."
        else:
            subject = f"🚫 Confirmed: Website Denied [{approval_id}]"
            color = "#F44336"
            status_text = "DENIED"
            message_text = f"The website <strong>{link}</strong> will remain blocked."

        body = f"""
        <html>
        <body style="font-family: Arial, sans-serif; color: #333;">
            <h2 style="color: {color};">Request {status_text}</h2>

            <p>Your response has been processed successfully.</p>

            <div style="background-color: #f5f5f5; padding: 15px; border-radius: 5px; margin: 20px 0;">
                <p><strong>Decision:</strong> {status_text}</p>
                <p><strong>Website:</strong> {link}</p>
                <p>{message_text}</p>
            </div>

            <p style="color: #666; font-size: 12px; margin-top: 30px;">
                Reference ID: {approval_id}<br>
                This is an automated confirmation from VigilMind Parental Control System.
            </p>
        </body>
        </html>
        """

        gmail.send_email(to=parent_email, subject=subject, body=body)
        print(f"✅ Confirmation email sent to parent")

    except Exception as e:
        print(f"Error sending confirmation email: {e}")


def email_monitoring_loop(check_interval: int = 60):
    """
    Background loop that monitors inbox for parent responses

    Args:
        check_interval: Seconds between inbox checks (default: 60)
    """
    global _monitoring_active

    print(f"📧 Email monitoring started (checking every {check_interval} seconds)")

    gmail = get_gmail_agent()
    processed_message_ids = set()

    while _monitoring_active:
        try:
            # Query for unread emails from parent with "VigilMind" in subject
            parent_email = get_parent_email()
            if not parent_email:
                print("⚠️ No parent email configured, skipping monitoring cycle")
                time.sleep(check_interval)
                continue

            # Get unread messages from parent
            query = f'is:unread from:{parent_email} subject:"VigilMind"'
            messages = gmail.get_messages(query=query, max_results=10)

            for message in messages:
                msg_id = message['id']

                # Skip if already processed
                if msg_id in processed_message_ids:
                    continue

                processed_message_ids.add(msg_id)

                print(f"\n📨 New parent response detected!")
                print(f"   Subject: {message['subject']}")

                # Process the response
                process_parent_response(message)

            # Clean up old processed IDs (keep last 1000)
            if len(processed_message_ids) > 1000:
                processed_message_ids = set(list(processed_message_ids)[-1000:])

        except Exception as e:
            print(f"Error in email monitoring loop: {e}")
            import traceback
            traceback.print_exc()

        time.sleep(check_interval)

    print("📧 Email monitoring stopped")


def start_email_monitoring(check_interval: int = 60):
    """
    Start the background email monitoring service

    Args:
        check_interval: Seconds between inbox checks (default: 60)
    """
    global _monitoring_thread, _monitoring_active

    if _monitoring_thread and _monitoring_thread.is_alive():
        print("⚠️ Email monitoring already running")
        return

    _monitoring_active = True
    _monitoring_thread = threading.Thread(
        target=email_monitoring_loop,
        args=(check_interval,),
        daemon=True
    )
    _monitoring_thread.start()
    print("✅ Email monitoring service started")


def stop_email_monitoring():
    """Stop the background email monitoring service"""
    global _monitoring_active

    _monitoring_active = False
    print("🛑 Stopping email monitoring...")