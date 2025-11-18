# VigilMind Parent Dashboard

A modern, intuitive web interface for parents to manage and configure the VigilMind parental control system.

## Features

### Configuration Management
- **Parent Email Setup**: Configure the email address for receiving approval requests
- **Monitoring Guidelines**: Define custom content standards and filtering rules
- **AI Auto-Approval**: Toggle whether the AI agent can automatically approve reasonable appeals
- **Initial Domain Lists**: Set up whitelisted and blacklisted domains during initial configuration

### Domain Management with Tag Input
- **Bubble/Tag Interface**: Add domains using an intuitive tag-based input system
  - Type a domain and press Enter to add it as a tag
  - Click the × button to remove a tag
  - Press Backspace on empty input to remove the last tag
- **Real-time Validation**: Domains are validated and normalized automatically
- **Visual Feedback**: Smooth animations when adding/removing domains

### Website Lists
- **Whitelisted Websites**: View all approved domains with timestamps and reasons
  - See when each domain was added
  - View the reason for whitelisting (AI-approved, parent-added, etc.)
  - Remove domains with a single click

- **Blacklisted Websites**: View all blocked domains
  - Track appeal usage for each blocked domain
  - See blocking reasons
  - Unblock domains easily

### Pending Approvals
- **Review System**: See all pending child appeal requests in one place
- **Detailed Information**:
  - Child's reason for requesting access
  - Timestamp of the request
  - AI decision (if escalated from AI denial)
- **Quick Actions**: Approve or deny appeals with visual feedback
- **Real-time Updates**: Badge shows count of pending approvals

## Prerequisites

- Node.js (v14 or higher)
- npm or yarn
- VigilMind backend server running on `http://127.0.0.1:5000`

## Installation

1. Navigate to the Parent Dashboard directory:
   ```bash
   cd Parent_Dashboard
   ```

2. Install dependencies:
   ```bash
   npm install
   ```

## Running the Dashboard

1. Ensure the VigilMind backend server is running:
   ```bash
   cd ../Big-Brother
   python new_server.py
   ```

2. Start the React development server:
   ```bash
   npm start
   ```

3. The dashboard will automatically open in your browser at `http://localhost:3000`

## Usage Guide

### First-Time Setup

1. **Configure Parent Email**
   - Enter your email address where you'll receive approval requests

2. **Set Monitoring Guidelines**
   - Describe the content standards you want enforced
   - Example: "Block violent content and inappropriate language. Allow educational resources and age-appropriate entertainment."

3. **Configure AI Auto-Approval** (Optional)
   - Enable this if you want the AI to automatically approve reasonable appeals
   - Disable to manually review all appeals

4. **Add Initial Domains** (Optional)
   - **Whitelist**: Add trusted domains (e.g., `wikipedia.org`, `khanacademy.org`)
   - **Blacklist**: Add domains to block (e.g., `example-gambling-site.com`)
   - Type domain and press Enter to add
   - Click × to remove

5. **Save Configuration**
   - Click "Save Configuration" to apply all settings

### Managing Domains

#### Adding Domains
1. Type the domain name in the tag input field
2. Press Enter to add it as a tag
3. Repeat for multiple domains
4. Click "Save Configuration" to sync with the database

#### Removing Domains
- **From Tag Input**: Click the × button on the tag
- **From Lists**: Click the "Remove" or "Unblock" button next to the domain

### Handling Appeal Requests

When your child requests access to blocked content:

1. Check the **Pending Approvals** section
2. Review the information:
   - URL being requested
   - Child's reason for the request
   - AI decision (if applicable)
3. Take action:
   - **Approve**: Grants access and moves domain to whitelist
   - **Deny**: Keeps the domain blocked

### Understanding AI Auto-Approval

**When Enabled:**
- AI evaluates appeals first
- Reasonable requests are auto-approved
- Denied requests can be escalated to you
- You receive notifications of auto-approvals

**When Disabled:**
- All appeals come directly to you
- Complete manual control
- Higher workload but more oversight

## API Endpoints Used

The dashboard communicates with these backend endpoints:

- `GET /config` - Fetch current configuration
- `PUT /config` - Update configuration
- `GET /whitelist` - Get whitelisted domains
- `POST /whitelist` - Add domain to whitelist
- `DELETE /whitelist/<domain>` - Remove from whitelist
- `GET /blacklist` - Get blacklisted domains
- `POST /blacklist` - Add domain to blacklist
- `DELETE /blacklist/<domain>` - Remove from blacklist
- `GET /pending-approvals` - Get pending approval requests
- `POST /approve-appeal` - Approve an appeal
- `POST /deny-appeal` - Deny an appeal

## Project Structure

```
Parent_Dashboard/
├── public/
│   └── index.html          # HTML template
├── src/
│   ├── components/
│   │   └── TagInput.js     # Tag-based domain input component
│   ├── App.js              # Main application component
│   ├── App.css             # Styles
│   └── index.js            # React entry point
├── package.json            # Dependencies and scripts
└── README.md              # This file
```

## Customization

### Changing API Base URL

If your backend runs on a different host/port, update the `API_BASE` constant in `src/App.js`:

```javascript
const API_BASE = 'http://your-server:port';
```

### Styling

Modify `src/App.css` to customize colors, fonts, and layout. The design uses CSS variables and modern flexbox/grid layouts.

## Troubleshooting

### Dashboard won't load
- Check that the backend server is running
- Verify the API_BASE URL is correct
- Check browser console for CORS errors

### Can't save configuration
- Ensure parent email and monitoring prompt are filled
- Check backend server logs for errors
- Verify MongoDB is running and accessible

### Domains not appearing
- Check that you clicked "Save Configuration"
- Verify domains are properly formatted (no http://, just domain)
- Check browser network tab for failed requests

## Browser Support

- Chrome/Edge (latest)
- Firefox (latest)
- Safari (latest)

## Security Notes

- This dashboard is intended for local network use
- Ensure the backend API has proper authentication in production
- Keep your parent email confidential
- Regularly review whitelisted and blacklisted domains

## Contributing

When adding new features:
1. Follow the existing component structure
2. Maintain responsive design
3. Add proper error handling
4. Update this README with new features

## License

Part of the VigilMind parental control system.
