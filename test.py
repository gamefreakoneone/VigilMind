from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient, ASCENDING
import openai
import os
from datetime import datetime
import threading
import queue
import time
from gmail_agent import GmailAgent

app = Flask(__name__)
CORS(app)

# MongoDB setup
MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')
client = MongoClient(MONGO_URI)
db = client['ParentalMonitorDB']

# Collections
whitelist_col = db['whitelist']
blacklist_col = db['blacklist']
appeals_col = db['appeals']  # NEW: Track appeals
pending_approvals_col = db['pending_approvals']  # NEW: Track parent approvals needed
logs_col = db['logs']
config_col = db['config']  # NEW: Store parent's monitoring preferences
desktop_events_col = db['desktop_events']  # NEW: Desktop monitoring logs

# Create indexes
appeals_col.create_index([('url', ASCENDING)])
pending_approvals_col.create_index([('approval_id', ASCENDING)], unique=True)

# Gmail agent
gmail_agent = GmailAgent()

# Event queue for async processing
event_queue = queue.Queue()

# ==================== CONFIGURATION ====================

def get_monitoring_config():
    """Get parent's monitoring configuration"""
    config = config_col.find_one({'type': 'monitoring_rules'})
    if not config:
        # Default config
        config = {
            'type': 'monitoring_rules',
            'parent_email': '',
            'monitoring_prompt': 'Block content with violence, adult themes, or inappropriate language for children under 13',
            'agent_can_auto_approve': False,  # Can agent auto-approve appeals?
            'desktop_monitoring_enabled': True,
            'screenshot_interval': 120,  # seconds
            'blocked_apps': ['steam.exe', 'discord.exe']  # Example
        }
        config_col.insert_one(config)
    return config

def update_monitoring_config(new_config):
    """Update monitoring configuration"""
    config_col.update_one(
        {'type': 'monitoring_rules'},
        {'$set': new_config},
        upsert=True
    )

# ==================== BROWSER MONITORING ====================

def analyze_content_with_llm(url, title, content):
    """Analyze if content is appropriate based on parent's rules"""
    config = get_monitoring_config()
    
    prompt = f"""You are monitoring content for a child based on these parent rules:
{config['monitoring_prompt']}

URL: {url}
Title: {title}
Content: {content[:3000]}

Respond with JSON only:
{{"appropriate": true/false, "reason": "brief explanation", "severity": "low/medium/high"}}"""

    try:
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        return eval(response.choices[0].message.content)
    except Exception as e:
        print(f"LLM Error: {e}")
        return {"appropriate": False, "reason": "Unable to verify", "severity": "medium"}

@app.route('/analyze', methods=['POST'])
def analyze_webpage():
    """Main endpoint for browser extension"""
    data = request.json
    url = data.get('url', '')
    title = data.get('title', '')
    content = data.get('content', '')
    
    from urllib.parse import urlparse
    domain = urlparse(url).netloc.lower()
    
    # Check whitelist/blacklist first
    if whitelist_col.find_one({'domain': domain}):
        return jsonify({'action': 'allow', 'reason': 'Whitelisted'})
    
    if blacklist_col.find_one({'domain': domain}):
        return jsonify({'action': 'block', 'reason': 'Blacklisted'})
    
    # Analyze with LLM
    analysis = analyze_content_with_llm(url, title, content)
    
    # Log the decision
    logs_col.insert_one({
        'url': url,
        'domain': domain,
        'action': 'block' if not analysis['appropriate'] else 'allow',
        'reason': analysis['reason'],
        'timestamp': datetime.now()
    })
    
    if analysis['appropriate']:
        whitelist_col.insert_one({'domain': domain, 'reason': analysis['reason']})
        return jsonify({'action': 'allow', 'reason': analysis['reason']})
    else:
        blacklist_col.insert_one({'domain': domain, 'reason': analysis['reason']})
        return jsonify({
            'action': 'block', 
            'reason': analysis['reason'],
            'appeal_enabled': True  # Tell extension to show appeal option
        })

# ==================== APPEAL SYSTEM ====================

@app.route('/appeal', methods=['POST'])
def submit_appeal():
    """Child submits appeal for blocked content"""
    data = request.json
    url = data.get('url', '')
    appeal_reason = data.get('appeal_reason', '')
    
    from urllib.parse import urlparse
    domain = urlparse(url).netloc.lower()
    
    # Create appeal record
    appeal_id = f"appeal_{int(time.time())}"
    appeal_record = {
        'appeal_id': appeal_id,
        'url': url,
        'domain': domain,
        'child_reason': appeal_reason,
        'timestamp': datetime.now(),
        'status': 'pending'  # pending, auto_approved, needs_parent, denied
    }
    appeals_col.insert_one(appeal_record)
    
    # Analyze the appeal with LLM
    config = get_monitoring_config()
    decision = evaluate_appeal_with_llm(url, appeal_reason, config)
    
    if decision['should_auto_approve'] and config['agent_can_auto_approve']:
        # Agent auto-approves
        whitelist_col.insert_one({'domain': domain, 'reason': f"Appeal approved: {decision['reason']}"})
        blacklist_col.delete_one({'domain': domain})
        
        appeals_col.update_one(
            {'appeal_id': appeal_id},
            {'$set': {'status': 'auto_approved', 'agent_decision': decision['reason']}}
        )
        
        # Still notify parent
        notify_parent_appeal_approved(url, appeal_reason, decision['reason'])
        
        return jsonify({
            'status': 'approved',
            'message': 'Your appeal was approved! Reloading page...',
            'reload': True
        })
    else:
        # Needs parent approval
        approval_id = f"approval_{int(time.time())}"
        pending_approvals_col.insert_one({
            'approval_id': approval_id,
            'appeal_id': appeal_id,
            'url': url,
            'domain': domain,
            'child_reason': appeal_reason,
            'timestamp': datetime.now(),
            'status': 'awaiting_parent'
        })
        
        # Send email to parent
        send_approval_request_email(approval_id, url, appeal_reason)
        
        return jsonify({
            'status': 'pending',
            'message': 'Your appeal has been sent to your parent for review.'
        })

def evaluate_appeal_with_llm(url, appeal_reason, config):
    """Let LLM evaluate if appeal is valid"""
    prompt = f"""A child has appealed a blocked website.

URL: {url}
Child's reason: {appeal_reason}

Parent's monitoring rules: {config['monitoring_prompt']}

Should this appeal be automatically approved?
Consider: Is this educational? For homework? Legitimate need?

Respond with JSON:
{{"should_auto_approve": true/false, "reason": "explanation"}}"""

    try:
        response = openai.chat.completions.create(
            model="gpt-4",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3
        )
        return eval(response.choices[0].message.content)
    except:
        return {"should_auto_approve": False, "reason": "Error evaluating appeal"}

# ==================== EMAIL INTEGRATION ====================

def send_approval_request_email(approval_id, url, child_reason):
    """Send email to parent requesting approval"""
    config = get_monitoring_config()
    parent_email = config.get('parent_email')
    
    if not parent_email:
        print("No parent email configured!")
        return
    
    approve_link = f"http://localhost:5000/approve/{approval_id}"
    deny_link = f"http://localhost:5000/deny/{approval_id}"
    
    body = f"""
    <h2>Website Access Appeal</h2>
    <p>Your child has requested access to a blocked website:</p>
    <p><strong>URL:</strong> {url}</p>
    <p><strong>Child's reason:</strong> {child_reason}</p>
    
    <p><a href="{approve_link}" style="background: green; color: white; padding: 10px 20px; text-decoration: none;">APPROVE</a></p>
    <p><a href="{deny_link}" style="background: red; color: white; padding: 10px 20px; text-decoration: none;">DENY</a></p>
    
    <p><em>You can also reply to this email with "APPROVE" or "DENY"</em></p>
    """
    
    gmail_agent.send_email(
        to=parent_email,
        subject=f"Appeal: Website Access Request",
        body=body
    )

def notify_parent_appeal_approved(url, child_reason, agent_reason):
    """Notify parent that agent auto-approved an appeal"""
    config = get_monitoring_config()
    parent_email = config.get('parent_email')
    
    if not parent_email:
        return
    
    body = f"""
    <h2>Appeal Auto-Approved</h2>
    <p>The monitoring agent approved your child's appeal:</p>
    <p><strong>URL:</strong> {url}</p>
    <p><strong>Child's reason:</strong> {child_reason}</p>
    <p><strong>Agent's decision:</strong> {agent_reason}</p>
    """
    
    gmail_agent.send_email(
        to=parent_email,
        subject="Appeal Auto-Approved",
        body=body
    )

@app.route('/approve/<approval_id>', methods=['GET'])
def approve_appeal(approval_id):
    """Parent approves via email link"""
    approval = pending_approvals_col.find_one({'approval_id': approval_id})
    
    if not approval:
        return "Invalid approval link", 404
    
    domain = approval['domain']
    
    # Whitelist the domain
    whitelist_col.insert_one({'domain': domain, 'reason': 'Parent approved appeal'})
    blacklist_col.delete_one({'domain': domain})
    
    # Update records
    pending_approvals_col.update_one(
        {'approval_id': approval_id},
        {'$set': {'status': 'approved', 'approved_at': datetime.now()}}
    )
    
    appeals_col.update_one(
        {'appeal_id': approval['appeal_id']},
        {'$set': {'status': 'parent_approved'}}
    )
    
    return "<h1>Appeal Approved!</h1><p>The website has been unblocked.</p>"

@app.route('/deny/<approval_id>', methods=['GET'])
def deny_appeal(approval_id):
    """Parent denies via email link"""
    approval = pending_approvals_col.find_one({'approval_id': approval_id})
    
    if not approval:
        return "Invalid approval link", 404
    
    # Update records
    pending_approvals_col.update_one(
        {'approval_id': approval_id},
        {'$set': {'status': 'denied', 'denied_at': datetime.now()}}
    )
    
    appeals_col.update_one(
        {'appeal_id': approval['appeal_id']},
        {'$set': {'status': 'parent_denied'}}
    )
    
    return "<h1>Appeal Denied</h1><p>The website remains blocked.</p>"

# ==================== DESKTOP MONITORING ====================

@app.route('/desktop/screenshot', methods=['POST'])
def receive_screenshot():
    """Receive screenshot from desktop monitor"""
    data = request.json
    app_name = data.get('app_name', '')
    window_title = data.get('window_title', '')
    screenshot_base64 = data.get('screenshot', '')
    
    # Check if app is in blocked list
    config = get_monitoring_config()
    if app_name.lower() in [app.lower() for app in config.get('blocked_apps', [])]:
        return jsonify({
            'action': 'terminate',
            'reason': f'{app_name} is blocked by parent'
        })
    
    # Analyze screenshot with vision model (if needed)
    # For now, just log it
    desktop_events_col.insert_one({
        'app_name': app_name,
        'window_title': window_title,
        'timestamp': datetime.now(),
        'screenshot_available': True
    })
    
    return jsonify({'action': 'allow'})

# ==================== PARENT DASHBOARD ====================

@app.route('/config', methods=['GET', 'POST'])
def manage_config():
    """Parent configures monitoring settings"""
    if request.method == 'POST':
        new_config = request.json
        update_monitoring_config(new_config)
        return jsonify({'success': True})
    else:
        return jsonify(get_monitoring_config())

@app.route('/dashboard/stats', methods=['GET'])
def get_dashboard_stats():
    """Get stats for parent dashboard"""
    return jsonify({
        'total_blocks': logs_col.count_documents({'action': 'block'}),
        'pending_appeals': appeals_col.count_documents({'status': 'pending'}),
        'whitelist_count': whitelist_col.count_documents({}),
        'blacklist_count': blacklist_col.count_documents({})
    })

# ==================== EMAIL MONITORING THREAD ====================

def monitor_parent_emails():
    """Background thread to check for parent email replies"""
    while True:
        try:
            # Check for emails with "APPROVE" or "DENY" in subject/body
            messages = gmail_agent.get_messages(query='subject:(Appeal OR approve OR deny)', max_results=5)
            
            for msg in messages:
                body_lower = msg['body'].lower()
                subject_lower = msg['subject'].lower()
                
                # Extract approval_id if present
                # Simple parsing - you'd want more robust extraction
                if 'approve' in body_lower or 'approve' in subject_lower:
                    # Try to find approval_id in body
                    # This is simplified - you'd need better parsing
                    pass
                    
                gmail_agent.mark_as_read(msg['id'])
            
            time.sleep(30)  # Check every 30 seconds
            
        except Exception as e:
            print(f"Email monitoring error: {e}")
            time.sleep(60)

# Start email monitoring in background
email_thread = threading.Thread(target=monitor_parent_emails, daemon=True)
email_thread.start()

if __name__ == '__main__':
    print("Starting Parental Monitoring Service...")
    app.run(host='localhost', port=5000, debug=True)