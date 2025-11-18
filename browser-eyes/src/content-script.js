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
        background: rgba(255, 255, 255, 0.98);
        z-index: 2147483647;
        display: flex;
        align-items: center;
        justify-content: center;
        font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
      }
      .loading-content {
        text-align: center;
      }
      .spinner {
        width: 50px;
        height: 50px;
        border: 4px solid #f3f3f3;
        border-top: 4px solid #667eea;
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
        color: #333;
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
  const article = new Readability(documentClone).parse();

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
        // Check if appeals are enabled AND haven't been used yet (max 1 appeal)
        const canAppeal = data.appeal_enabled && (data.appeals_used || 0) < 1;

        if (canAppeal) {
          showBlockPageWithAppeal(data.reason, data.appeals_used || 0);
        } else {
          blockPage(data.reason);
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
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          display: flex;
          align-items: center;
          justify-content: center;
          min-height: 100vh;
          color: white;
          padding: 20px;
        }
        .container {
          text-align: center;
          padding: 40px;
          background: rgba(255, 255, 255, 0.1);
          border-radius: 20px;
          backdrop-filter: blur(10px);
          max-width: 600px;
          box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
        }
        .icon {
          font-size: 80px;
          margin-bottom: 20px;
        }
        h1 {
          margin: 0 0 20px 0;
          font-size: 32px;
        }
        p {
          font-size: 18px;
          margin: 10px 0;
          opacity: 0.9;
        }
        .reason {
          background: rgba(255, 255, 255, 0.2);
          padding: 15px;
          border-radius: 10px;
          margin: 20px 0;
          font-size: 16px;
        }
        .appeal-section {
          margin-top: 30px;
          padding-top: 30px;
          border-top: 2px solid rgba(255, 255, 255, 0.3);
        }
        .appeal-section h2 {
          font-size: 20px;
          margin-bottom: 15px;
        }
        textarea {
          width: 100%;
          padding: 15px;
          border: none;
          border-radius: 10px;
          font-size: 16px;
          font-family: inherit;
          resize: vertical;
          min-height: 100px;
          margin-bottom: 15px;
        }
        button {
          background: white;
          color: #667eea;
          border: none;
          padding: 15px 30px;
          font-size: 16px;
          border-radius: 25px;
          cursor: pointer;
          font-weight: bold;
          margin: 5px;
          transition: transform 0.2s;
        }
        button:hover {
          transform: scale(1.05);
        }
        button.secondary {
          background: rgba(255, 255, 255, 0.2);
          color: white;
        }
        .status-message {
          margin-top: 20px;
          padding: 15px;
          border-radius: 10px;
          display: none;
        }
        .status-message.show {
          display: block;
        }
        .status-message.success {
          background: rgba(76, 175, 80, 0.3);
        }
        .status-message.pending {
          background: rgba(255, 152, 0, 0.3);
        }
      </style>
    </head>
    <body>
      <div class="container">
        <div class="icon">🛡️</div>
        <h1>Content Blocked</h1>
        <p>This website has been blocked by your parental controls.</p>
        <div class="reason">
          <strong>Reason:</strong> ${reason}
        </div>

        <div class="appeal-section" id="appeal-section">
          <h2>Need this website?</h2>
          <p style="font-size: 16px; opacity: 0.9;">Explain why you need access and it will be reviewed</p>
          <textarea id="appeal-reason" placeholder="Example: I need this website for my science homework assignment on climate change"></textarea>
          <button id="submit-btn">Submit Appeal</button>
          <button id="back-btn" class="secondary">Go Back</button>
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
        statusDiv.textContent = 'Appeal approved! ' + data.reason;
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
      } else {
        // Appeal is pending parent approval
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
        body {
          margin: 0;
          padding: 0;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Arial, sans-serif;
          background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
          display: flex;
          align-items: center;
          justify-content: center;
          min-height: 100vh;
          color: white;
        }
        .container {
          text-align: center;
          padding: 40px;
          background: rgba(255, 255, 255, 0.1);
          border-radius: 20px;
          backdrop-filter: blur(10px);
          max-width: 600px;
          box-shadow: 0 8px 32px rgba(0, 0, 0, 0.1);
        }
        .icon {
          font-size: 80px;
          margin-bottom: 20px;
        }
        h1 {
          margin: 0 0 20px 0;
          font-size: 32px;
        }
        p {
          font-size: 18px;
          margin: 10px 0;
          opacity: 0.9;
        }
        .reason {
          background: rgba(255, 255, 255, 0.2);
          padding: 15px;
          border-radius: 10px;
          margin: 20px 0;
          font-size: 16px;
        }
        button {
          background: white;
          color: #667eea;
          border: none;
          padding: 15px 30px;
          font-size: 16px;
          border-radius: 25px;
          cursor: pointer;
          font-weight: bold;
          margin-top: 20px;
          transition: transform 0.2s;
        }
        button:hover {
          transform: scale(1.05);
        }
      </style>
    </head>
    <body>
      <div class="container">
        <div class="icon">🛡️</div>
        <h1>Content Blocked</h1>
        <p>This website has been blocked by your parental controls.</p>
        <div class="reason">
          <strong>Reason:</strong> ${reason}
        </div>
        <p>If you believe this is a mistake, please talk to your parent or guardian.</p>
        <button onclick="history.back()">Go Back</button>
      </div>
    </body>
    </html>
  `;
}