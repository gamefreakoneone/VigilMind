# VigilMind - Parental Control System

VigilMind is a comprehensive parental control solution designed to monitor and manage children's digital activity across desktop applications and web browsing. It leverages AI to analyze content and enforce parental guidelines in real-time.

## System Architecture

The project consists of three main components:

1.  **Big-Brother (Backend & Desktop Monitor)**:
    -   A Flask-based server that handles API requests, manages the MongoDB database, and performs AI analysis using OpenAI.
    -   Includes a Desktop Monitoring script that tracks active windows, takes screenshots of unknown applications, and terminates those that violate guidelines.
2.  **Parent_Dashboard (Frontend)**:
    -   A React-based web interface for parents to configure settings, view activity logs, review blocked applications, and handle appeals.
3.  **browser-eyes (Browser Extension)**:
    -   A browser extension that monitors web content and integrates with the backend for analysis.

## Prerequisites

Before setting up, ensure you have the following installed:

-   **Node.js** (v16 or higher) & **npm**
-   **Python** (v3.8 or higher)
-   **MongoDB** (Local instance or Atlas URI)

## Installation & Setup

### 1. Backend Setup (Big-Brother)

1.  Navigate to the `Big-Brother` directory.
2.  Create a `.env` file with the following configuration:
    ```env
    OPENAI_API_KEY=your_openai_key
    MONGO_URI=mongodb://localhost:27017/
    PARENT_EMAIL=parent@example.com
    EMAIL_PASSWORD=your_app_password
    HOST=127.0.0.1
    PORT=5000
    ```
3.  Install Python dependencies:
    ```bash
    pip install flask flask-cors pymongo openai psutil pillow pywin32 win10toast youtube-transcript-api agents pydantic
    ```
4.  Start the backend server:
    ```bash
    python new_server.py
    ```

### 2. Frontend Setup (Parent_Dashboard)

1.  Navigate to the `Parent_Dashboard` directory.
2.  Install dependencies:
    ```bash
    npm install
    ```
3.  Start the development server:
    ```bash
    npm start
    ```
    The dashboard will be available at `http://localhost:3000`.

### 3. Browser Extension Setup (browser-eyes)

1.  Navigate to the `browser-eyes` directory.
2.  Install dependencies:
    ```bash
    npm install
    ```
3.  Build the extension:
    ```bash
    npm run build
    ```
4.  Load the extension in your browser:
    -   **Chrome/Edge**: Go to Extensions > Manage Extensions. Enable "Developer mode". Click "Load unpacked" and select the `dist` folder inside `browser-eyes`.

### 4. Desktop Monitor Setup

To enable desktop application monitoring:

1.  Open a new terminal as **Administrator**.
2.  Navigate to `Big-Brother/System_Monitoring`.
3.  Run the monitor script:
    ```bash
    python active_window_test.py
    ```

## Usage

-   **Dashboard**: Use the Parent Dashboard to set monitoring guidelines and review blocked content.
-   **Monitoring**: The Desktop Monitor runs in the background, checking active windows. If a non-whitelisted app is detected, it captures a screenshot for AI analysis.
-   **Alerts**: If an app violates guidelines, it is terminated, and a notification is shown.
-   **Appeals**: Children can appeal blocks, which parents can review in the dashboard.

## Known bugs
- Desktop Monitoring only works on Single desktop setups and not a multi monitor setup. 

## Future features
- Agent Child Assistant: Rather than simply blocking the child, the agent can assist the child in finding alternatives and provide a safer browsing experience.
- Desktop Notification when parent approves
- Time Analysis
- Safer gaurdrails against prompt engineering