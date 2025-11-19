import React, { useState, useEffect } from 'react';
import axios from 'axios';
import TagInput from './components/TagInput';
import './App.css';

const API_BASE = 'http://127.0.0.1:5000';

function App() {
  // Configuration state
  const [config, setConfig] = useState({
    parent_email: '',
    monitoring_prompt: '',
    agent_can_auto_approve: false,
  });

  // Domain lists state
  const [whitelistDomains, setWhitelistDomains] = useState([]);
  const [blacklistDomains, setBlacklistDomains] = useState([]);

  // Existing lists from database
  const [existingWhitelist, setExistingWhitelist] = useState([]);
  const [existingBlacklist, setExistingBlacklist] = useState([]);

  // Desktop app lists
  const [blacklistedDesktopApps, setBlacklistedDesktopApps] = useState([]);
  const [whitelistedDesktopApps, setWhitelistedDesktopApps] = useState([]);

  // Pending approvals
  const [pendingApprovals, setPendingApprovals] = useState([]);

  // UI state
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState(null);

  // Load initial data
  useEffect(() => {
    loadData();
  }, []);

  // Auto-refresh pending approvals and domain lists every 5 seconds
  useEffect(() => {
    const refreshInterval = setInterval(async () => {
      try {
        const [whitelistRes, blacklistRes, approvalsRes, desktopBlacklistRes, desktopWhitelistRes] = await Promise.all([
          axios.get(`${API_BASE}/whitelist`),
          axios.get(`${API_BASE}/blacklist`),
          axios.get(`${API_BASE}/pending-approvals`),
          axios.get(`${API_BASE}/desktop/blacklist`),
          axios.get(`${API_BASE}/desktop/whitelist`),
        ]);

        setExistingWhitelist(whitelistRes.data || []);
        setExistingBlacklist(blacklistRes.data || []);
        setPendingApprovals(approvalsRes.data || []);
        setBlacklistedDesktopApps(desktopBlacklistRes.data || []);
        setWhitelistedDesktopApps(desktopWhitelistRes.data || []);
      } catch (error) {
        console.error('Error refreshing data:', error);
      }
    }, 120000); // Refresh every 2 minutes

    // Cleanup interval on component unmount
    return () => clearInterval(refreshInterval);
  }, []);

  const loadData = async () => {
    try {
      setLoading(true);
      const [configRes, whitelistRes, blacklistRes, approvalsRes, desktopBlacklistRes, desktopWhitelistRes] = await Promise.all([
        axios.get(`${API_BASE}/config`),
        axios.get(`${API_BASE}/whitelist`),
        axios.get(`${API_BASE}/blacklist`),
        axios.get(`${API_BASE}/pending-approvals`),
        axios.get(`${API_BASE}/desktop/blacklist`),
        axios.get(`${API_BASE}/desktop/whitelist`),
      ]);

      setConfig({
        parent_email: configRes.data.parent_email || '',
        monitoring_prompt: configRes.data.monitoring_prompt || '',
        agent_can_auto_approve: configRes.data.agent_can_auto_approve || false,
      });

      setExistingWhitelist(whitelistRes.data || []);
      setExistingBlacklist(blacklistRes.data || []);
      setPendingApprovals(approvalsRes.data || []);
      setBlacklistedDesktopApps(desktopBlacklistRes.data || []);
      setWhitelistedDesktopApps(desktopWhitelistRes.data || []);
    } catch (error) {
      console.error('Error loading data:', error);
      showMessage('Error loading dashboard data', 'error');
    } finally {
      setLoading(false);
    }
  };

  const showMessage = (text, type = 'success') => {
    setMessage({ text, type });
    setTimeout(() => setMessage(null), 5000);
  };

  const handleSaveConfiguration = async () => {
    if (!config.parent_email || !config.monitoring_prompt) {
      showMessage('Please fill in all required fields', 'error');
      return;
    }

    try {
      setSaving(true);

      // Save configuration
      await axios.put(`${API_BASE}/config`, config);

      // Add whitelist domains
      for (const domain of whitelistDomains) {
        try {
          await axios.post(`${API_BASE}/whitelist`, { domain });
        } catch (err) {
          console.error(`Error adding ${domain} to whitelist:`, err);
        }
      }

      // Add blacklist domains
      for (const domain of blacklistDomains) {
        try {
          await axios.post(`${API_BASE}/blacklist`, { domain });
        } catch (err) {
          console.error(`Error adding ${domain} to blacklist:`, err);
        }
      }

      showMessage('Configuration saved successfully!', 'success');

      // Clear the input domains and reload data
      setWhitelistDomains([]);
      setBlacklistDomains([]);
      await loadData();
    } catch (error) {
      console.error('Error saving configuration:', error);
      showMessage('Error saving configuration', 'error');
    } finally {
      setSaving(false);
    }
  };

  const handleRemoveFromWhitelist = async (domain) => {
    try {
      await axios.delete(`${API_BASE}/whitelist/${encodeURIComponent(domain)}`);
      showMessage(`Removed ${domain} from whitelist`, 'success');
      await loadData();
    } catch (error) {
      console.error('Error removing from whitelist:', error);
      showMessage('Error removing domain', 'error');
    }
  };

  const handleRemoveFromBlacklist = async (domain) => {
    try {
      await axios.delete(`${API_BASE}/blacklist/${encodeURIComponent(domain)}`);
      showMessage(`Removed ${domain} from blacklist`, 'success');
      await loadData();
    } catch (error) {
      console.error('Error removing from blacklist:', error);
      showMessage('Error removing domain', 'error');
    }
  };

  const handleApproveAppeal = async (approval_id, link) => {
    try {
      await axios.post(`${API_BASE}/approve-appeal`, { approval_id });
      showMessage(`Approved access to ${link}`, 'success');
      await loadData();
    } catch (error) {
      console.error('Error approving appeal:', error);
      showMessage('Error approving appeal', 'error');
    }
  };

  const handleDenyAppeal = async (approval_id) => {
    try {
      await axios.post(`${API_BASE}/deny-appeal`, { approval_id });
      showMessage('Appeal denied', 'info');
      await loadData();
    } catch (error) {
      console.error('Error denying appeal:', error);
      showMessage('Error denying appeal', 'error');
    }
  };

  const handleApproveDesktopApp = async (app_name) => {
    try {
      await axios.delete(`${API_BASE}/desktop/blacklist/${encodeURIComponent(app_name)}`);
      showMessage(`Approved ${app_name}`, 'success');
      await loadData();
    } catch (error) {
      console.error('Error approving desktop app:', error);
      showMessage('Error approving desktop app', 'error');
    }
  };

  const formatTimestamp = (timestamp) => {
    if (!timestamp) return 'N/A';
    const date = new Date(timestamp);
    return date.toLocaleString();
  };

  if (loading) {
    return (
      <div className="loading">
        <div className="spinner"></div>
      </div>
    );
  }

  return (
    <div className="App">
      <header className="header">
        <div className="header-content">
          <h1>VigilMind Parent Dashboard</h1>
          <p>Manage your child's online safety and monitoring settings</p>
        </div>
      </header>

      <div className="container">
        {message && (
          <div className={`alert alert-${message.type}`}>
            <span>{message.text}</span>
          </div>
        )}

        <div className="dashboard-grid">
          {/* Configuration Section */}
          <div className="card">
            <div className="card-header">
              <h2 className="card-title">Configuration Settings</h2>
            </div>

            <div className="form-group">
              <label className="form-label">Parent Email *</label>
              <input
                type="email"
                className="form-input"
                placeholder="parent@example.com"
                value={config.parent_email}
                onChange={(e) => setConfig({ ...config, parent_email: e.target.value })}
              />
            </div>

            <div className="form-group">
              <label className="form-label">Monitoring Guidelines *</label>
              <textarea
                className="form-textarea"
                placeholder="Describe the content standards you want enforced (e.g., 'Block violent content and inappropriate language. Allow educational resources and age-appropriate entertainment.')"
                value={config.monitoring_prompt}
                onChange={(e) => setConfig({ ...config, monitoring_prompt: e.target.value })}
              />
            </div>

            <div className="form-group">
              <label className="toggle-label">
                <span className="form-label" style={{ marginBottom: 0 }}>
                  Allow AI Agent to Auto-Approve Appeals
                </span>
                <label className="toggle-switch">
                  <input
                    type="checkbox"
                    checked={config.agent_can_auto_approve}
                    onChange={(e) =>
                      setConfig({ ...config, agent_can_auto_approve: e.target.checked })
                    }
                  />
                  <span className="slider"></span>
                </label>
              </label>
              <p style={{ fontSize: '0.875rem', color: '#718096', marginTop: '0.5rem' }}>
                When enabled, the AI can automatically approve reasonable appeals without your review
              </p>
            </div>

            <div className="form-group">
              <label className="form-label">Initial Whitelisted Domains</label>
              <TagInput
                tags={whitelistDomains}
                setTags={setWhitelistDomains}
                placeholder="Type domains to whitelist (e.g., wikipedia.org) and press Enter..."
              />
            </div>

            <div className="form-group">
              <label className="form-label">Initial Blacklisted Domains</label>
              <TagInput
                tags={blacklistDomains}
                setTags={setBlacklistDomains}
                placeholder="Type domains to blacklist (e.g., example.com) and press Enter..."
              />
            </div>

            <button
              className="btn btn-primary"
              onClick={handleSaveConfiguration}
              disabled={saving}
            >
              {saving ? 'Saving...' : 'Save Configuration'}
            </button>
          </div>

          {/* Pending Approvals Section */}
          <div className="card">
            <div className="card-header">
              <h2 className="card-title">Pending Approvals</h2>
              <span className="badge pending">{pendingApprovals.length}</span>
            </div>

            {pendingApprovals.length === 0 ? (
              <div className="empty-state">
                <div className="empty-state-icon">✓</div>
                <div className="empty-state-text">No pending approvals</div>
                <div className="empty-state-subtext">
                  Appeal requests will appear here for your review
                </div>
              </div>
            ) : (
              <div className="list-container">
                {pendingApprovals.map((approval) => (
                  <div key={approval.approval_id} className="approval-item">
                    <div className="approval-header">
                      <div className="approval-link">{approval.link}</div>
                      <div className="approval-time">
                        {formatTimestamp(approval.timestamp)}
                      </div>
                    </div>

                    <div className="approval-reason">
                      "{approval.child_reason}"
                    </div>

                    {approval.escalated_from_ai && (
                      <div style={{ fontSize: '0.875rem', color: '#718096', marginBottom: '1rem' }}>
                        AI Decision: {approval.ai_decision}
                      </div>
                    )}

                    <div className="approval-actions">
                      <button
                        className="btn btn-success btn-small"
                        onClick={() => handleApproveAppeal(approval.approval_id, approval.link)}
                      >
                        ✓ Approve
                      </button>
                      <button
                        className="btn btn-danger btn-small"
                        onClick={() => handleDenyAppeal(approval.approval_id)}
                      >
                        ✗ Deny
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Whitelisted Websites */}
          <div className="card">
            <div className="card-header">
              <h2 className="card-title">Whitelisted Websites</h2>
              <span className="badge">{existingWhitelist.length}</span>
            </div>

            {existingWhitelist.length === 0 ? (
              <div className="empty-state">
                <div className="empty-state-icon">📝</div>
                <div className="empty-state-text">No whitelisted websites yet</div>
                <div className="empty-state-subtext">
                  Approved websites will appear here
                </div>
              </div>
            ) : (
              <div className="list-container">
                {existingWhitelist.map((item, index) => (
                  <div key={index} className="list-item">
                    <div className="list-item-info">
                      <div className="list-item-domain">{item.link}</div>
                      <div className="list-item-meta">
                        Added: {formatTimestamp(item.added_at)} • {item.parental_reasoning || item.reason}
                      </div>
                    </div>
                    <button
                      className="btn btn-danger btn-small"
                      onClick={() => handleRemoveFromWhitelist(item.link)}
                    >
                      Remove
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Blacklisted Websites */}
          <div className="card">
            <div className="card-header">
              <h2 className="card-title">Blacklisted Websites</h2>
              <span className="badge">{existingBlacklist.length}</span>
            </div>

            {existingBlacklist.length === 0 ? (
              <div className="empty-state">
                <div className="empty-state-icon">🛡️</div>
                <div className="empty-state-text">No blacklisted websites yet</div>
                <div className="empty-state-subtext">
                  Blocked websites will appear here
                </div>
              </div>
            ) : (
              <div className="list-container">
                {existingBlacklist.map((item, index) => (
                  <div key={index} className="list-item">
                    <div className="list-item-info">
                      <div className="list-item-domain">{item.link}</div>
                      <div className="list-item-meta">
                        Added: {formatTimestamp(item.added_at)} • {item.parental_reasoning || item.reason}
                        {item.appeals > 0 && ` • Appeals used: ${item.appeals}`}
                      </div>
                    </div>
                    <button
                      className="btn btn-success btn-small"
                      onClick={() => handleRemoveFromBlacklist(item.link)}
                    >
                      Unblock
                    </button>
                  </div>
                ))}
              </div>
            )}
          </div>

          {/* Blacklisted Desktop Applications */}
          <div className="card">
            <div className="card-header">
              <h2 className="card-title">Blacklisted Desktop Applications</h2>
              <span className="badge pending">{blacklistedDesktopApps.length}</span>
            </div>

            {blacklistedDesktopApps.length === 0 ? (
              <div className="empty-state">
                <div className="empty-state-icon">💻</div>
                <div className="empty-state-text">No blacklisted applications</div>
                <div className="empty-state-subtext">
                  Blocked desktop apps will appear here for your review
                </div>
              </div>
            ) : (
              <div className="list-container">
                {blacklistedDesktopApps.map((item, index) => (
                  <div key={index} className="approval-item">
                    <div className="approval-header">
                      <div className="approval-link" style={{ textTransform: 'uppercase' }}>
                        {item.app}
                      </div>
                      <div className="approval-time">
                        {formatTimestamp(item.added_at)}
                      </div>
                    </div>

                    {item.parental_reasoning && (
                      <div className="approval-reason">
                        {item.parental_reasoning}
                      </div>
                    )}

                    {item.screenshot_id && (
                      <div style={{ marginTop: '1rem', marginBottom: '1rem' }}>
                        <img
                          src={`${API_BASE}/desktop/screenshot/${item.screenshot_id}`}
                          alt="Screenshot"
                          style={{
                            maxWidth: '100%',
                            borderRadius: '8px',
                            border: '1px solid #e2e8f0',
                            cursor: 'pointer'
                          }}
                          onClick={() => {
                            window.open(
                              `${API_BASE}/desktop/screenshot/${item.screenshot_id}`,
                              '_blank'
                            );
                          }}
                        />
                      </div>
                    )}

                    <div className="approval-actions">
                      <button
                        className="btn btn-success btn-small"
                        onClick={() => handleApproveDesktopApp(item.app)}
                      >
                        ✓ Approve & Unblock
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
