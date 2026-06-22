FILE = '/workspaces/taxgpt_tanzania/frontend/index_fixed.html'

with open(FILE, 'r') as f:
    content = f.read()

# 1. Remove old auth-section
idx = content.find('<div class="auth-section"')
if idx != -1:
    end_idx = content.find('\n  <div class="tools-section">', idx)
    if end_idx != -1:
        content = content[:idx] + content[end_idx+1:]
        print('✅ Old auth-section removed')
    else:
        print('⚠️ Could not find end of auth-section')
else:
    print('✅ auth-section already removed')

# 2. Replace sidebar-footer with bottom user menu
OLD_FOOTER = '  <div class="sidebar-footer">TaxGPT Tanzania v2.0</div>'
NEW_BOTTOM = '''  <div class="sidebar-bottom" id="sidebarBottom">
    <div id="guestAuth" style="padding:12px 14px;display:flex;gap:8px;flex-direction:column;">
      <a href="/login" class="auth-btn auth-btn-primary" style="margin-bottom:0;">Login</a>
      <a href="/signup" class="auth-btn" style="margin-bottom:0;">Sign Up</a>
    </div>
    <div id="userAuth" style="display:none;">
      <div class="user-menu-trigger" id="userMenuTrigger" onclick="toggleUserMenu()">
        <div class="user-avatar" id="userAvatar">O</div>
        <div class="user-menu-info">
          <div class="user-email" id="userEmail">user@email.com</div>
          <div class="user-plan-badge" id="userPlanBadge">Free</div>
        </div>
        <svg id="userMenuChevron" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="color:#64748b;flex-shrink:0;transition:transform 0.2s;"><polyline points="18 15 12 9 6 15"></polyline></svg>
      </div>
      <div class="user-menu-dropdown" id="userMenuDropdown" style="display:none;">
        <div class="user-menu-header">
          <div style="font-size:12px;color:#64748b;font-weight:500;padding:4px 0 6px;" id="userMenuEmail"></div>
          <div id="userCountryBadge" style="font-size:11px;color:#dfff00;margin-bottom:2px;"></div>
          <div id="userRoleBadge" style="font-size:11px;color:#64748b;"></div>
        </div>
        <a href="/account" class="user-menu-item">⚙️ My Account</a>
        <a href="/admin" class="user-menu-item" id="adminLink" style="display:none;">🔒 Admin Panel</a>
        <div class="user-menu-divider"></div>
        <button class="user-menu-item user-menu-logout" onclick="logout()">↪ Log out</button>
      </div>
    </div>
  </div>'''

if 'sidebar-bottom' in content:
    print('✅ Bottom user menu already present')
elif OLD_FOOTER in content:
    content = content.replace(OLD_FOOTER, NEW_BOTTOM)
    print('✅ Bottom user menu added')
else:
    print('ERROR: Could not find sidebar-footer')

# 3. Add CSS
NEW_CSS = """
.sidebar-bottom{border-top:1px solid #161f3a;position:relative}
.user-menu-trigger{display:flex;align-items:center;gap:10px;padding:12px 14px;cursor:pointer;transition:background 0.15s}
.user-menu-trigger:hover{background:#111c44}
.user-avatar{width:32px;height:32px;border-radius:50%;background:#dfff00;color:#0a0f00;font-weight:700;font-size:13px;display:flex;align-items:center;justify-content:center;flex-shrink:0}
.user-menu-info{flex:1;min-width:0}
.user-email{font-size:13px;font-weight:600;color:#e2e8f0;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.user-plan-badge{font-size:11px;font-weight:600;color:#64748b;margin-top:1px}
.user-plan-badge.premium{color:#dfff00}
.user-menu-dropdown{position:absolute;bottom:100%;left:8px;right:8px;background:#0c1635;border:1px solid #1e293b;border-radius:12px;padding:8px;box-shadow:0 -8px 32px rgba(0,0,0,0.4);z-index:100}
.user-menu-header{padding:6px 8px 10px;border-bottom:1px solid #161f3a;margin-bottom:6px}
.user-menu-item{display:block;width:100%;text-align:left;padding:9px 10px;border-radius:8px;font-size:14px;color:#94a3b8;font-weight:500;cursor:pointer;background:none;border:none;font-family:inherit;text-decoration:none;transition:background 0.15s,color 0.15s}
.user-menu-item:hover{background:#161f3a;color:#e2e8f0}
.user-menu-divider{height:1px;background:#161f3a;margin:6px 0}
.user-menu-logout{color:#f87171 !important}
.user-menu-logout:hover{background:#450a0a !important}
"""
style_end = content.find('</style>')
if style_end != -1:
    content = content[:style_end] + NEW_CSS + content[style_end:]
    print('✅ CSS added')

# 4. Update checkAuth to populate new elements
OLD_CHECK = "      document.getElementById('guestAuth').style.display = 'none';\n      document.getElementById('userAuth').style.display = 'block';\n      document.getElementById('userEmail').textContent = data.email;\n      if (data.country) document.getElementById('userCountryBadge').textContent = '🌍 ' + data.country;\n      if (data.role) document.getElementById('userRoleBadge').textContent = 'Role: ' + data.role;"
NEW_CHECK = """      document.getElementById('guestAuth').style.display = 'none';
      document.getElementById('userAuth').style.display = 'block';
      document.getElementById('userEmail').textContent = data.email;
      if (document.getElementById('userMenuEmail')) document.getElementById('userMenuEmail').textContent = data.email;
      const av = document.getElementById('userAvatar');
      if (av) av.textContent = (data.email || 'U')[0].toUpperCase();
      const planBadge = document.getElementById('userPlanBadge');
      if (planBadge) {
        if (data.is_premium) { planBadge.textContent = '⭐ Pro'; planBadge.className = 'user-plan-badge premium'; }
        else { planBadge.textContent = 'Free'; planBadge.className = 'user-plan-badge'; }
      }
      if (data.country) document.getElementById('userCountryBadge').textContent = '🌍 ' + data.country;
      if (data.role) document.getElementById('userRoleBadge').textContent = 'Role: ' + data.role;"""

if 'userMenuEmail' in content:
    print('✅ checkAuth already updated')
elif OLD_CHECK in content:
    content = content.replace(OLD_CHECK, NEW_CHECK)
    print('✅ checkAuth updated')
else:
    print('⚠️ checkAuth block not found with exact match — skipping')

# 5. Remove old myAccountBtn show line if present
content = content.replace("      document.getElementById('myAccountBtn').style.display = 'block';\n", '')

# 6. Add toggleUserMenu JS
TOGGLE_JS = """
function toggleUserMenu() {
  const dropdown = document.getElementById('userMenuDropdown');
  const chevron = document.getElementById('userMenuChevron');
  const isOpen = dropdown.style.display !== 'none';
  dropdown.style.display = isOpen ? 'none' : 'block';
  chevron.style.transform = isOpen ? '' : 'rotate(180deg)';
}
document.addEventListener('click', function(e) {
  const trigger = document.getElementById('userMenuTrigger');
  const dropdown = document.getElementById('userMenuDropdown');
  if (dropdown && trigger && !trigger.contains(e.target) && !dropdown.contains(e.target)) {
    dropdown.style.display = 'none';
    const chevron = document.getElementById('userMenuChevron');
    if (chevron) chevron.style.transform = '';
  }
});
"""
if 'function toggleUserMenu' in content:
    print('✅ toggleUserMenu already present')
else:
    idx = content.rfind('</script>')
    content = content[:idx] + TOGGLE_JS + content[idx:]
    print('✅ toggleUserMenu JS added')

with open(FILE, 'w') as f:
    f.write(content)
print('\n✅ Done! Saved:', FILE)
