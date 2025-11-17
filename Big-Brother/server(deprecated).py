from flask import Flask, request, jsonify
from flask_cors import CORS
from pymongo import MongoClient, ASCENDING
import openai
import os
from urllib.parse import urlparse
import json
from datetime import datetime
import threading
import time

# Essentially logic is whitelist and blacklist is domain wide, while graylist is page specific 


app = Flask(__name__)
CORS(app)

# In-memory lock for preventing duplicate LLM calls
analysis_locks = {}
locks_lock = threading.Lock()

MONGO_URI = os.getenv('MONGO_URI', 'mongodb://localhost:27017/')
client = MongoClient(MONGO_URI)
db = client['NorthlightDB']

# Remember
#Blacklist: Domain wide block
# Graylist: Page spcific / domain block based on content
# Whitelist: Domain wide allow

whitelist_col = db['whitelist']
graylist_col = db['graylist']
blacklist_col = db['blacklist']

graylist_desktop_col = db['graylist_desktop']
whitelist_desktop = db['whitelist_desktop']

analysis_cache_col = db['analysis_cache']
logs_col = db['logs']

# Create indexes for faster lookups (what was the point of creating indexes??)
whitelist_col.create_index([('link', ASCENDING)], unique=True)
graylist_col.create_index([('link', ASCENDING)], unique=True)
blacklist_col.create_index([('link', ASCENDING)], unique=True)

# gray
analysis_cache_col.create_index([('link', ASCENDING)])
logs_col.create_index([('timestamp', ASCENDING)])

# OpenAI setup
openai.api_key = os.getenv('OPENAI_API_KEY')

def get_domain(url):
    parsed = urlparse(url)
    return parsed.netloc.lower()

# Essentially 2 functions, called block domain and block page, so domain for more general, page for specific url


def is_whitelisted(link):
    return whitelist_col.find_one({'link': link}) is not None

def is_graylisted(domain):
    return graylist_col.find_one({'domain': domain}) is not None

def is_blacklisted(link):
    """Check if link is in blacklist"""
    return blacklist_col.find_one({'link': link}) is not None

def add_to_whitelist(link, reason='Manual'):
    """Add link to whitelist"""
    try:
        whitelist_col.insert_one({
            'link': link,
            'added_at': datetime.now(),
            'type': 'domain',
            'reason': reason
        })
        # Remove from blacklist if exists
        blacklist_col.delete_one({'link': link})
        return True
    except:
        return False

def add_to_graylist(link, reason='Manual'):
    """Add link to graylist"""
    try:
        graylist_col.insert_one({
            'link': link,
            'added_at': datetime.now(),
            'type': '',
            'reason': reason
        })
        # Remove from whitelist if exists
        whitelist_col.delete_one({'domain': domain})
        return True
    except:
        return False

def add_to_blacklist(link, reason='Manual'):
    """Add link to blacklist"""
    try:
        blacklist_col.insert_one({
            'link': link,
            'added_at': datetime.now(),
            'type': 'domain',
            'reason': reason
        })
        # Remove from whitelist if exists
        whitelist_col.delete_one({'link': link})
        return True
    except:
        return False

# Technically useful for online setup but not right now
def get_cached_analysis(domain):
    """Get cached analysis result"""
    cache = analysis_cache_col.find_one({'domain': domain})
    if cache:
        return cache.get('result')
    return None

def cache_analysis(domain, result): # I dont think we need this
    """Cache analysis result"""
    analysis_cache_col.update_one(
        {'domain': domain},
        {'$set': {
            'domain': domain,
            'result': result,
            'timestamp': datetime.now()
        }},
        upsert=True
    )

def log_request(url, domain, action, reason):
    """Log analysis request"""
    logs_col.insert_one({
        'url': url,
        'domain': domain,
        'action': action,
        'reason': reason,
        'timestamp': datetime.now()
    })


# Add functionality to make it multimodal if needed. Also to make the call to ban a domain or page specifically
def check_content_with_llm(title, content, url):
    """Use OpenAI to analyze content appropriateness"""
    # Truncate content if too long
    max_content = 3000
    truncated_content = content[:max_content] if len(content) > max_content else content
    
    prompt = f"""You are a content safety filter for children. Analyze if this webpage is appropriate for children under 13.

URL: {url}
Title: {title}
Content: {truncated_content}

Check for:
- Violence or gore
- Sexual content
- Hate speech or discrimination
- Drug/alcohol promotion
- Inappropriate language
- Gambling
- Dangerous activities

Respond with JSON only:
{{"appropriate": true/false, "reason": "brief explanation"}}"""

    # Update this. IT does not work anymore
    try:
        response = openai.chat.completions.create(
            model="gpt-5-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=150
        )
        
        result = json.loads(response.choices[0].message.content)
        return result
    except Exception as e:
        print(f"LLM Error: {e}")
        return {"appropriate": False, "reason": "Unable to verify content safety"}

def acquire_analysis_lock(domain):
    """Try to acquire lock for analyzing a domain"""
    with locks_lock:
        if domain in analysis_locks:
            return False  # Already being analyzed
        analysis_locks[domain] = threading.Lock()
        analysis_locks[domain].acquire()
        return True

def release_analysis_lock(domain):
    """Release lock for a domain"""
    with locks_lock:
        if domain in analysis_locks:
            analysis_locks[domain].release()
            del analysis_locks[domain]

def wait_for_analysis(domain, timeout=10):
    """Wait for another thread to finish analyzing this domain"""
    start_time = time.time()
    while time.time() - start_time < timeout:
        # Check if analysis is complete (result in cache)
        cached = get_cached_analysis(domain)
        if cached:
            return cached
        time.sleep(0.5)
    return None

@app.route('/analyze', methods=['POST'])
def analyze():
    data = request.json
    url = data.get('url', '')
    title = data.get('title', '')
    content = data.get('content', '')
    
    domain = get_domain(url)
    
    # Check whitelist first
    if is_whitelisted(domain):
        log_request(url, domain, 'allowed', 'Whitelisted')
        return jsonify({
            'status': 'allowed',
            'reason': 'Whitelisted domain',
            'action': 'allow'
        })
    
    # Check blacklist
    if is_blacklisted(domain):
        log_request(url, domain, 'blocked', 'Blacklisted')
        return jsonify({
            'status': 'blocked',
            'reason': 'Blacklisted domain',
            'action': 'block'
        })
    
    # Check cache ?? It is for locking lookup
    cached = get_cached_analysis(domain)
    if cached:
        action = 'allow' if cached['appropriate'] else 'block'
        log_request(url, domain, action, f"Cached: {cached['reason']}")
        return jsonify({
            'status': 'allowed' if cached['appropriate'] else 'blocked',
            'reason': cached['reason'],
            'action': action,
            'cached': True
        })
    
    # Try to acquire lock for this domain
    if not acquire_analysis_lock(domain):
        # Another request is analyzing this domain, wait for result
        print(f"Domain {domain} already being analyzed, waiting...")
        waited_result = wait_for_analysis(domain)
        if waited_result:
            action = 'allow' if waited_result['appropriate'] else 'block'
            log_request(url, domain, action, f"Waited: {waited_result['reason']}")
            return jsonify({
                'status': 'allowed' if waited_result['appropriate'] else 'blocked',
                'reason': waited_result['reason'],
                'action': action,
                'waited': True
            })
        # If wait timeout, fall through to analyze anyway
    
    try:
        # Analyze with LLM
        print(f"Analyzing domain {domain} with LLM...")
        analysis = check_content_with_llm(title, content, url)
        
        # Cache the result
        cache_analysis(domain, analysis)
        
        if analysis['appropriate']:
            add_to_whitelist(domain, analysis['reason']) # Change to whitelist
            log_request(url, domain, 'allowed', analysis['reason'])
            
            return jsonify({
                'status': 'allowed',
                'reason': analysis['reason'],
                'action': 'allow'
            })
        else:
            add_to_blacklist(domain, analysis['reason']) # Change to graylist for appeals
            log_request(url, domain, 'blocked', analysis['reason'])
            
            return jsonify({
                'status': 'blocked',
                'reason': analysis['reason'],
                'action': 'block'
            })
    finally:
        # Always release the lock
        release_analysis_lock(domain)

@app.route('/whitelist', methods=['GET', 'POST', 'DELETE'])
def manage_whitelist():
    """Manage whitelist"""
    if request.method == 'POST':
        domain = request.json.get('domain', '').lower()
        reason = request.json.get('reason', 'Manual addition')
        if add_to_whitelist(domain, reason):
            return jsonify({'success': True, 'message': f'Added {domain} to whitelist'})
        return jsonify({'success': False, 'message': 'Failed to add domain'}), 400
    
    elif request.method == 'DELETE':
        domain = request.json.get('domain', '').lower()
        result = whitelist_col.delete_one({'domain': domain})
        return jsonify({'success': result.deleted_count > 0})
    
    # GET
    domains = list(whitelist_col.find({}, {'_id': 0}))
    return jsonify(domains)

@app.route('/blacklist', methods=['GET', 'POST', 'DELETE'])
def manage_blacklist():
    """Manage blacklist"""
    if request.method == 'POST':
        domain = request.json.get('domain', '').lower()
        reason = request.json.get('reason', 'Manual addition')
        if add_to_blacklist(domain, reason):
            return jsonify({'success': True, 'message': f'Added {domain} to blacklist'})
        return jsonify({'success': False, 'message': 'Failed to add domain'}), 400
    
    elif request.method == 'DELETE':
        domain = request.json.get('domain', '').lower()
        result = blacklist_col.delete_one({'domain': domain})
        return jsonify({'success': result.deleted_count > 0})
    
    # GET
    domains = list(blacklist_col.find({}, {'_id': 0}))
    return jsonify(domains)

@app.route('/logs', methods=['GET'])
def get_logs():
    """Get recent logs"""
    limit = int(request.args.get('limit', 100))
    logs = list(logs_col.find({}, {'_id': 0}).sort('timestamp', -1).limit(limit))
    return jsonify(logs)

@app.route('/stats', methods=['GET'])
def get_stats():
    """Get statistics"""
    stats = {
        'whitelist_count': whitelist_col.count_documents({}),
        'blacklist_count': blacklist_col.count_documents({}),
        'total_requests': logs_col.count_documents({}),
        'blocked_requests': logs_col.count_documents({'action': 'blocked'}),
        'allowed_requests': logs_col.count_documents({'action': 'allowed'})
    }
    return jsonify(stats)

@app.route('/health', methods=['GET'])
def health():
    """Health check endpoint"""
    return jsonify({'status': 'healthy', 'mongodb': 'connected'})

if __name__ == '__main__':
    # Initialize with some safe domains
    safe_domains = ['google.com', 'youtube.com', 'wikipedia.org', 
                    'khanacademy.org', 'pbskids.org', 'localhost']
    for domain in safe_domains:
        try:
            add_to_whitelist(domain, 'Default safe site')
        except:
            pass  # Already exists
    
    app.run(host='localhost', port=5000, debug=True)


def main():
    """
    Entry point for the service. Validates configuration, optionally seeds
    safe domains, and starts the Flask app.
    """
    parser = argparse.ArgumentParser(description="Northlight content filter API")
    parser.add_argument("--host", default=os.getenv("HOST", "127.0.0.1"),
                        help="Host interface to bind (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", "5000")),
                        help="Port to bind (default: 5000)")
    parser.add_argument("--debug", action="store_true",
                        help="Enable Flask debug mode")
    parser.add_argument("--no-seed", dest="seed", action="store_false",
                        help="Do not seed default safe domains")
    parser.add_argument("--seed-only", action="store_true",
                        help="Seed defaults then exit (no server)")
    args = parser.parse_args()

    # --- Validate critical env/config ---
    if not openai.api_key:
        print("WARNING: OPENAI_API_KEY not set. LLM checks will fail.", file=sys.stderr)

    # --- Check Mongo connectivity early (fast fail) ---
    try:
        client.admin.command("ping")
    except Exception as e:
        print(f"ERROR: Could not connect to MongoDB at {MONGO_URI}\n{e}", file=sys.stderr)
        sys.exit(1)

    # --- Optional seeding of default safe domains ---
    if args.seed:
        safe_domains = [
            "google.com", "youtube.com", "wikipedia.org",
            "khanacademy.org", "pbskids.org", "localhost"
        ]
        for domain in safe_domains:
            try:
                add_to_whitelist(domain, "Default safe site")
            except Exception:
                pass  # already exists or race; safe to ignore
        print(f"Seeded {len(safe_domains)} default domains into whitelist.")

    if args.seed_only:
        print("Seed complete. Exiting due to --seed-only.")
        return

    # --- Start Flask app ---
    app.run(host=args.host, port=args.port, debug=args.debug)




if __name__ == "__main__":
    main()