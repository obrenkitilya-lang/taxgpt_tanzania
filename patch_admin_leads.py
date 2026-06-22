import re

FILE = '/workspaces/taxgpt_tanzania/frontend/index_fixed.html'

with open(FILE, 'r') as f:
    content = f.read()

errors = []

LEADS_HTML = '''
      <div class="calc-card" style="margin-bottom:20px;">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px;">
          <h3 style="margin:0;">🏢 Business Setup Leads</h3>
          <span id="leadsCount" style="background:#1e293b;color:#94a3b8;font-size:13px;padding:4px 12px;border-radius:20px;">Loading...</span>
        </div>
        <div id="adminLeadsList" style="max-height:500px;overflow-y:auto;">
          <p style="color:#64748b;text-align:center;">Loading leads...</p>
        </div>
      </div>

'''

REGISTERED_USERS_ANCHOR = '      <div class="calc-card" style="margin-bottom:20px;">\n        <h3 style="margin-bottom:16px;">👥 Registered Users</h3>'

if 'adminLeadsList' in content:
    print('✅ Business Leads HTML already present')
elif REGISTERED_USERS_ANCHOR in content:
    content = content.replace(REGISTERED_USERS_ANCHOR, LEADS_HTML + REGISTERED_USERS_ANCHOR)
    print('✅ Business Leads card added')
else:
    errors.append('Could not find Registered Users anchor')

if 'loadAdminLeads()' in content:
    print('✅ loadAdminLeads() call already present')
else:
    if 'loadAdminAuditLogs();' in content:
        content = content.replace('loadAdminAuditLogs();', 'loadAdminAuditLogs();\n  loadAdminLeads();')
        print('✅ loadAdminLeads() call added')
    else:
        errors.append('Could not find loadAdminAuditLogs()')

NEW_JS = '''
function loadAdminLeads() {
  const list = document.getElementById('adminLeadsList');
  const count = document.getElementById('leadsCount');
  if (!list) return;
  fetch('/api/admin/business-leads', { credentials: 'include' })
  .then(r => r.json())
  .then(leads => {
    if (!leads || leads.length === 0) {
      list.innerHTML = '<p style="color:#64748b;text-align:center;">No leads yet</p>';
      if (count) count.textContent = '0 leads';
      return;
    }
    if (count) count.textContent = leads.length + ' lead' + (leads.length !== 1 ? 's' : '');
    const statusColors = {new:'#dfff00', contacted:'#60a5fa', converted:'#4ade80', closed:'#94a3b8'};
    list.innerHTML = '';
    leads.forEach(lead => {
      const div = document.createElement('div');
      div.style.cssText = 'padding:16px;border-bottom:1px solid #1e293b;display:grid;grid-template-columns:1fr auto;gap:12px;align-items:start;';
      const color = statusColors[lead.status] || '#94a3b8';
      div.innerHTML = `
        <div>
          <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px;">
            <span style="font-weight:700;color:white;font-size:15px;">${escapeHtml(lead.name)}</span>
            <span style="background:#1e293b;color:#dfff00;font-size:11px;padding:2px 8px;border-radius:10px;">${escapeHtml(lead.business_type)}</span>
            <span style="background:#1e293b;color:${color};font-size:11px;padding:2px 8px;border-radius:10px;text-transform:uppercase;">${escapeHtml(lead.status)}</span>
          </div>
          <div style="color:#94a3b8;font-size:13px;margin-bottom:4px;">📧 ${escapeHtml(lead.email)} &nbsp;|&nbsp; 📞 ${escapeHtml(lead.phone)} &nbsp;|&nbsp; 🌍 ${escapeHtml(lead.country||'N/A')}</div>
          ${lead.business_description ? `<div style="color:#64748b;font-size:12px;margin-top:4px;font-style:italic;">"${escapeHtml(lead.business_description)}"</div>` : ''}
          <div style="color:#475569;font-size:11px;margin-top:6px;">Submitted: ${escapeHtml(lead.created_at||'')}</div>
        </div>
        <div style="display:flex;flex-direction:column;gap:6px;min-width:130px;">
          <select onchange="updateLeadStatus(${lead.id}, this.value)" style="background:#0f172a;color:white;border:1px solid #334155;padding:6px 8px;border-radius:8px;font-size:12px;cursor:pointer;">
            <option value="new"${lead.status==='new'?' selected':''}>🟡 New</option>
            <option value="contacted"${lead.status==='contacted'?' selected':''}>🔵 Contacted</option>
            <option value="converted"${lead.status==='converted'?' selected':''}>🟢 Converted</option>
            <option value="closed"${lead.status==='closed'?' selected':''}>⚫ Closed</option>
          </select>
        </div>`;
      list.appendChild(div);
    });
  }).catch(() => { list.innerHTML = '<p style="color:#f87171;text-align:center;">Error loading leads</p>'; });
}

function updateLeadStatus(leadId, status) {
  fetch('/api/admin/business-leads/' + leadId + '/status', {
    method: 'PUT', headers: {'Content-Type':'application/json'}, credentials: 'include',
    body: JSON.stringify({status: status})
  }).then(r => r.json()).then(data => {
    if (data.error) alert('Error: ' + data.error);
    else loadAdminLeads();
  });
}

function togglePremium(userId, currentPremium) {
  const newStatus = !currentPremium;
  fetch('/api/admin/users/' + userId + '/premium', {
    method: 'PUT', headers: {'Content-Type':'application/json'}, credentials: 'include',
    body: JSON.stringify({is_premium: newStatus})
  }).then(r => r.json()).then(data => {
    if (data.error) alert('Error: ' + data.error);
    else loadAdminUsersDetailed();
  });
}
'''

if 'function loadAdminLeads()' in content:
    print('✅ JS functions already present')
else:
    idx = content.rfind('</script>')
    if idx == -1:
        errors.append('Could not find </script>')
    else:
        content = content[:idx] + NEW_JS + content[idx:]
        print('✅ JS functions injected')

if errors:
    print('\n⚠️  Issues:', errors)
else:
    print('\n✅ All patches applied!')

with open(FILE, 'w') as f:
    f.write(content)
print('✅ Saved:', FILE)
