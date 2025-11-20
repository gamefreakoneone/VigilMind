// Chrome extension content-script.js

import { Readability } from "@mozilla/readability";

showLoadingScreen();

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", extractAndSend);
} else {
  extractAndSend();
}

function showLoadingScreen() {
  const overlay = document.createElement("div");
  overlay.id = "parental-supervisor-overlay";
  overlay.innerHTML = `
    <style>
      #parental-supervisor-overlay {
        position: fixed;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: #F0F9FF;
        z-index: 2147483647;
        display: flex;
        align-items: center;
        justify-content: center;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
      }
      .loading-content {
        text-align: center;
        background: white;
        padding: 40px;
        border-radius: 24px;
        box-shadow: 0 10px 25px rgba(0,0,0,0.05);
      }
      .spinner {
        width: 50px;
        height: 50px;
        border: 4px solid #E1E8ED;
        border-top: 4px solid #3B82F6;
        border-radius: 50%;
        animation: spin 1s linear infinite;
        margin: 0 auto 20px;
      }
      @keyframes spin {
        0% { transform: rotate(0deg); }
        100% { transform: rotate(360deg); }
      }
      .loading-text {
        font-size: 18px;
        color: #334155;
        font-weight: 500;
      }
    </style>
    <div class="loading-content">
      <div class="spinner"></div>
      <div class="loading-text">Checking content safety...</div>
    </div>
  `;
  document.documentElement.appendChild(overlay);
}

function removeLoadingScreen() {
  const overlay = document.getElementById("parental-supervisor-overlay");
  if (overlay) {
    overlay.remove();
  }
}

function extractAndSend() {
  console.log("extractAndSend called for:", window.location.href);
  const documentClone = document.cloneNode(true);

  let article = null;
  try {
    article = new Readability(documentClone).parse();
  } catch (error) {
    console.warn("Readability parsing failed, using fallback content extraction:", error.message);
    // article remains null, will use fallback content below
  }

  const pageData = {
    url: window.location.href,
    title: document.title,
    content: article ? article.textContent : document.body.innerText,
    timestamp: Date.now(),
  };

  fetch("http://localhost:5000/analyze", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(pageData),
  })
    .then((response) => response.json())
    .then((data) => {
      console.log("Analysis result:", data);

      if (data.action === 'block') {
        // Check if appeals haven't been used yet (max 1 appeal)
        const canAppeal = (data.appeals_used || 0) < 1;

        // Use "reasoning" (child-safe) instead of "reason" or "parental_reasoning"
        const displayReason = data.reasoning || data.reason || "This content has been blocked.";

        if (canAppeal) {
          showBlockPageWithAppeal(displayReason, data.appeals_used || 0);
        } else {
          blockPage(displayReason);
        }
      } else {
        // Allowed - remove loading screen
        removeLoadingScreen();
      }
    })
    .catch((error) => {
      console.error("Error:", error);
      blockPage("Error analyzing content. Please try again later.");
    });
}

function showBlockPageWithAppeal(reason, appealsUsed = 0) {
  console.log('showBlockPageWithAppeal called with reason:', reason, 'appealsUsed:', appealsUsed);

  document.documentElement.innerHTML = `
    <!DOCTYPE html>
    <html>
    <head>
      <title>Content Blocked</title>
      <style>
        * {
          margin: 0;
          padding: 0;
          box-sizing: border-box;
        }
        body {
          font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
          background: #F0F9FF;
          display: flex;
          align-items: center;
          justify-content: center;
          min-height: 100vh;
          color: #334155;
          padding: 20px;
        }
        .container {
          text-align: center;
          padding: 50px;
          background: white;
          border-radius: 24px;
          max-width: 600px;
          width: 100%;
          box-shadow: 0 20px 40px rgba(0, 0, 0, 0.08);
          border: 1px solid #E2E8F0;
        }
        .icon {
          margin-bottom: 24px;
        }
        h1 {
          margin: 0 0 16px 0;
          font-size: 28px;
          color: #1E293B;
          font-weight: 700;
        }
        p {
          font-size: 16px;
          margin: 8px 0;
          color: #64748B;
          line-height: 1.5;
        }
        .reason {
          background: #EFF6FF;
          border: 1px solid #DBEAFE;
          color: #1E40AF;
          padding: 16px;
          border-radius: 12px;
          margin: 24px 0;
          font-size: 15px;
          text-align: left;
        }
        .appeal-section {
          margin-top: 32px;
          padding-top: 32px;
          border-top: 1px solid #E2E8F0;
        }
        .appeal-section h2 {
          font-size: 18px;
          margin-bottom: 12px;
          color: #334155;
        }
        textarea {
          width: 100%;
          padding: 16px;
          border: 2px solid #E2E8F0;
          border-radius: 12px;
          font-size: 15px;
          font-family: inherit;
          resize: vertical;
          min-height: 120px;
          margin-bottom: 20px;
          transition: border-color 0.2s;
          outline: none;
        }
        textarea:focus {
          border-color: #3B82F6;
        }
        button {
          background: #3B82F6;
          color: white;
          border: none;
          padding: 14px 32px;
          font-size: 16px;
          border-radius: 50px;
          cursor: pointer;
          font-weight: 600;
          margin: 8px;
          transition: all 0.2s;
          box-shadow: 0 4px 12px rgba(59, 130, 246, 0.25);
        }
        button:hover {
          background: #2563EB;
          transform: translateY(-1px);
          box-shadow: 0 6px 16px rgba(59, 130, 246, 0.35);
        }
        button:disabled {
          background: #94A3B8;
          transform: none;
          cursor: not-allowed;
        }
        button.secondary {
          background: white;
          color: #64748B;
          border: 2px solid #E2E8F0;
          box-shadow: none;
        }
        button.secondary:hover {
          background: #F8FAFC;
          border-color: #CBD5E1;
          color: #334155;
        }
        .status-message {
          margin-top: 24px;
          padding: 16px;
          border-radius: 12px;
          display: none;
          font-size: 15px;
        }
        .status-message.show {
          display: block;
        }
        .status-message.success {
          background: #DCFCE7;
          color: #166534;
          border: 1px solid #BBF7D0;
        }
        .status-message.pending {
          background: #FEF3C7;
          color: #92400E;
          border: 1px solid #FDE68A;
        }
      </style>
    </head>
    <body>
      <div class="container">
        <div class="icon">
          <svg width="80" height="80" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 22C12 22 20 18 20 12V5L12 2L4 5V12C4 18 12 22 12 22Z" fill="#3B82F6"/>
            <path d="M12 8V13" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M12 16H12.01" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </div>
        <h1>Page Blocked</h1>
        <p>This website is not available right now.</p>
        <div class="reason">
          <strong>Why?</strong> ${reason}
        </div>

        <div class="appeal-section" id="appeal-section">
          <h2>Need access for something important?</h2>
          <p style="font-size: 14px; margin-bottom: 16px;">Tell us why you need to visit this page.</p>
          <textarea id="appeal-reason" placeholder="I need this for my homework because..."></textarea>
          <div>
            <button id="submit-btn">Ask for Permission</button>
            <button id="back-btn" class="secondary">Go Back</button>
          </div>
        </div>

        <div id="status-message" class="status-message"></div>
      </div>
    </body>
    </html>
  `;

  // Attach event listeners after DOM is created
  const submitBtn = document.getElementById('submit-btn');
  const backBtn = document.getElementById('back-btn');

  submitBtn.addEventListener('click', function() {
    console.log('submitAppeal() called');
    const appealReason = document.getElementById('appeal-reason').value.trim();

    if (!appealReason) {
      alert('Please explain why you need this website');
      return;
    }

    // Disable the form elements immediately
    const textarea = document.getElementById('appeal-reason');

    textarea.disabled = true;
    submitBtn.disabled = true;
    submitBtn.style.opacity = '0.5';
    submitBtn.style.cursor = 'not-allowed';

    const statusDiv = document.getElementById('status-message');
    statusDiv.textContent = 'Submitting appeal...';
    statusDiv.className = 'status-message show pending';

    console.log('Sending appeal request to server...');

    fetch('http://localhost:5000/appeal', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        url: window.location.href,
        title: document.title,
        appeal_reason: appealReason
      })
    })
    .then(response => {
      console.log('Received response:', response);
      return response.json();
    })
    .then(data => {
      console.log('Appeal response data:', data);

      if (data.status === 'approved') {
        // AI approved the appeal
        const approvalMessage = data.reasoning || data.reason || 'Your appeal has been approved!';
        statusDiv.textContent = 'Appeal approved! ' + approvalMessage;
        statusDiv.className = 'status-message show success';

        // Remove the appeals section
        const appealSection = document.getElementById('appeal-section');
        if (appealSection) {
          appealSection.remove();
        }

        if (data.reload) {
          setTimeout(() => {
            window.location.reload();
          }, 2000);
        }
      } else if (data.status === 'ai_denied') {
        // AI denied - offer escalation to parent
        const denialMessage = data.reasoning || data.reason || 'Your appeal was not approved.';
        statusDiv.textContent = 'The AI agent reviewed your request but decided to keep this website blocked. Reason: ' + denialMessage;
        statusDiv.className = 'status-message show';
        statusDiv.style.background = 'rgba(255, 152, 0, 0.3)';

        // Re-enable form
        textarea.disabled = false;
        submitBtn.disabled = false;
        submitBtn.style.opacity = '1';
        submitBtn.style.cursor = 'pointer';

        // Change submit button to "Ask Parent Anyway"
        submitBtn.textContent = 'Ask Parent Anyway';

        // Update the click handler to escalate
        submitBtn.onclick = function() {
          submitBtn.disabled = true;
          submitBtn.style.opacity = '0.5';
          textarea.disabled = true;

          statusDiv.textContent = 'Sending request to parent...';
          statusDiv.className = 'status-message show pending';

          fetch('http://localhost:5000/escalate-to-parent', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              appeal_id: data.appeal_id,
              url: window.location.href,
              appeal_reason: appealReason
            })
          })
          .then(response => response.json())
          .then(escalateData => {
            statusDiv.textContent = escalateData.reason;
            statusDiv.className = 'status-message show pending';

            // Remove appeal section
            const appealSection = document.getElementById('appeal-section');
            if (appealSection) {
              appealSection.remove();
            }
          })
          .catch(error => {
            console.error('Error escalating to parent:', error);
            statusDiv.textContent = 'Error sending request to parent. Please try again.';
            submitBtn.disabled = false;
            submitBtn.style.opacity = '1';
            textarea.disabled = false;
          });
        };
      } else if (data.status === 'pending_parent') {
        // Sent directly to parent (no AI evaluation) or after escalation
        statusDiv.textContent = data.reason;
        statusDiv.className = 'status-message show pending';

        // Remove the entire appeals section
        const appealSection = document.getElementById('appeal-section');
        if (appealSection) {
          appealSection.remove();
        }

        // Update the back button text
        backBtn.textContent = 'Return to Previous Page';
      }
    })
    .catch(error => {
      console.error('Error submitting appeal:', error);
      statusDiv.textContent = 'Error submitting appeal. Please try again.';
      statusDiv.className = 'status-message show';

      // Re-enable form on error
      textarea.disabled = false;
      submitBtn.disabled = false;
      submitBtn.style.opacity = '1';
      submitBtn.style.cursor = 'pointer';
    });
  });

  backBtn.addEventListener('click', function() {
    history.back();
  });
}

function blockPage(reason) {
  // Original block page without appeal option
  document.documentElement.innerHTML = `
    <!DOCTYPE html>
    <html>
    <head>
      <title>Content Blocked</title>
      <style>
        * {
          margin: 0;
          padding: 0;
          box-sizing: border-box;
        }
        body {
          font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
          background: #F0F9FF;
          display: flex;
          align-items: center;
          justify-content: center;
          min-height: 100vh;
          color: #334155;
          padding: 20px;
        }
        .container {
          text-align: center;
          padding: 50px;
          background: white;
          border-radius: 24px;
          max-width: 600px;
          width: 100%;
          box-shadow: 0 20px 40px rgba(0, 0, 0, 0.08);
          border: 1px solid #E2E8F0;
        }
        .icon {
          margin-bottom: 24px;
        }
        h1 {
          margin: 0 0 16px 0;
          font-size: 28px;
          color: #1E293B;
          font-weight: 700;
        }
        p {
          font-size: 16px;
          margin: 8px 0;
          color: #64748B;
          line-height: 1.5;
        }
        .reason {
          background: #EFF6FF;
          border: 1px solid #DBEAFE;
          color: #1E40AF;
          padding: 16px;
          border-radius: 12px;
          margin: 24px 0;
          font-size: 15px;
          text-align: left;
        }
        button {
          background: #3B82F6;
          color: white;
          border: none;
          padding: 14px 32px;
          font-size: 16px;
          border-radius: 50px;
          cursor: pointer;
          font-weight: 600;
          margin-top: 24px;
          transition: all 0.2s;
          box-shadow: 0 4px 12px rgba(59, 130, 246, 0.25);
        }
        button:hover {
          background: #2563EB;
          transform: translateY(-1px);
          box-shadow: 0 6px 16px rgba(59, 130, 246, 0.35);
        }
      </style>
    </head>
    <body>
      <div class="container">
        <div class="icon">
          <svg width="80" height="80" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M12 22C12 22 20 18 20 12V5L12 2L4 5V12C4 18 12 22 12 22Z" fill="#3B82F6"/>
            <path d="M12 8V13" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
            <path d="M12 16H12.01" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
          </svg>
        </div>
        <h1>Page Blocked</h1>
        <p>This website is not available right now.</p>
        <div class="reason">
          <strong>Why?</strong> ${reason}
        </div>
        <p style="margin-top: 24px; font-size: 14px;">If you believe this is a mistake, please talk to your parent or guardian.</p>
        <button onclick="history.back()">Go Back</button>
      </div>
    </body>
    </html>
  `;
}